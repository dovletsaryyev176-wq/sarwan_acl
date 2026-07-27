import json
import logging
import sys
import time

from flask import g, got_request_exception, request, session

from . import config, writer

logger = logging.getLogger('audit')


def _setup_logging(app):
    """
    Вывод в stdout: systemd уже собирает его в journald, который сам заботится
    о ротации и хранении. Ни файлов, ни прав доступа, ни риска забить диск.

        journalctl -u sarwan.service -f
        journalctl -u sarwan.service --since "1 hour ago" | grep ERROR
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    root = logging.getLogger()
    if not any(getattr(h, '_audit', False) for h in root.handlers):
        handler._audit = True
        root.addHandler(handler)
        root.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    # У werkzeug и waitress свои логгеры, они наследуют root — этого достаточно.
    app.logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))


def _capture_exception(sender, exception, **extra):
    """
    Запоминает необработанное исключение, чтобы положить его текст в журнал.

    Такой ответ Flask отдаёт как HTML-страницу 500, поля error в нём нет —
    без этого перехвата в таблице остался бы голый код 500 без причины.

    Сам traceback пишет штатный логгер Flask, здесь он намеренно не
    дублируется. Подключено сигналом, а не errorhandler'ом: сигнал не
    вмешивается в формирование ответа, поведение приложения не меняется.
    """
    try:
        g._audit_exception = '{}: {}'.format(type(exception).__name__, exception)
    except Exception:
        pass


def _should_audit():
    if request.method not in config.AUDITED_METHODS:
        return False
    path = request.path or ''
    return not path.startswith(config.SKIP_PATH_PREFIXES)


def _actor():
    """Кто выполнил действие: сотрудник, клиент приложения или аноним."""
    client_id = getattr(g, 'client_id', None)
    if client_id:
        return 'client', None, client_id, None, None

    user_id = session.get('user_id')
    if user_id:
        name, role = writer.user_info(user_id)
        return 'staff', user_id, None, name, role or session.get('role')

    return 'anon', None, None, None, None


def _request_body():
    """
    Тело запроса.

    Читаем только JSON. Для multipart тело не трогаем вообще: в
    api/worker/workers.py есть загрузка фото сотрудников, и обращение к телу
    затянуло бы файл в память и могло помешать разбору request.files.
    Вызывается уже после роута, поэтому данные берутся из кеша Werkzeug.
    """
    content_type = (request.content_type or '').split(';')[0].strip().lower()

    if content_type == 'application/json':
        try:
            return content_type, writer.mask_body(request.get_data(cache=True, as_text=True))
        except Exception:
            return content_type, None

    if not content_type:
        return None, None

    try:
        size = request.content_length
    except Exception:
        size = None
    return content_type, json.dumps({'content_type': content_type, 'content_length': size},
                                    ensure_ascii=False)


def _error_text(response):
    """
    Текст ошибки из тела ответа — это и есть сообщения тех 52 мест,
    где исключение перехватывается и возвращается как {'error': str(e)}.

    Тело читаем крайне осторожно: у send_file и send_from_directory ответ идёт
    в режиме passthrough, и обращение к его данным выбрасывает RuntimeError,
    ломая отдачу файлов и выгрузку Excel.
    """
    if response.status_code < 400:
        return None

    # Необработанное исключение: ответ — HTML-страница Flask, текст берём
    # из перехваченного сигналом объекта исключения
    captured = getattr(g, '_audit_exception', None)

    if getattr(response, 'direct_passthrough', False) or response.is_streamed:
        return captured
    if 'application/json' not in (response.content_type or ''):
        return captured

    try:
        raw = response.get_data(as_text=True)
    except Exception:
        return captured

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            text = parsed.get('error') or parsed.get('message') or raw
        else:
            text = raw
    except Exception:
        text = raw

    return str(text or captured or '')[:config.MAX_ERROR_CHARS] or None


def init_audit(app):
    """Подключает журнал действий. Единственная точка входа."""
    _setup_logging(app)
    got_request_exception.connect(_capture_exception, app)

    if not config.ENABLED:
        logger.info('audit disabled via AUDIT_ENABLED')
        from .routes import audit_bp
        app.register_blueprint(audit_bp, url_prefix='/api/admin')
        return

    @app.before_request
    def _audit_start():
        g._audit_started_at = time.perf_counter()

    @app.after_request
    def _audit_finish(response):
        # Весь хук под защитой: исключение здесь превратило бы успешный
        # ответ в 500 сразу на всех эндпоинтах.
        try:
            if not _should_audit():
                return response

            started = getattr(g, '_audit_started_at', None)
            duration_ms = int((time.perf_counter() - started) * 1000) if started else 0

            actor_type, user_id, client_id, actor_name, role = _actor()
            content_type, body = _request_body()
            error_text = _error_text(response)

            path = request.full_path or request.path
            if path.endswith('?'):
                path = path[:-1]

            writer.write({
                'actor_type': actor_type,
                'user_id': user_id,
                'client_id': client_id,
                'actor_name': actor_name,
                'role': role,
                'method': request.method,
                'path': path[:config.MAX_PATH_CHARS],
                'endpoint': request.endpoint,
                'status_code': response.status_code,
                'duration_ms': duration_ms,
                'ip': request.remote_addr,
                'user_agent': (request.user_agent.string or '')[:config.MAX_UA_CHARS] or None,
                'content_type': content_type,
                'request_body': body,
                'error_text': error_text,
            })

            if response.status_code >= 400:
                logger.warning(
                    '%s %s -> %s (%s ms) actor=%s:%s %s',
                    request.method, path, response.status_code, duration_ms,
                    actor_type, user_id or client_id or '-', error_text or '',
                )
        except Exception as e:
            try:
                logger.warning('audit hook failed: %s', e)
            except Exception:
                pass

        return response

    from .routes import audit_bp
    app.register_blueprint(audit_bp, url_prefix='/api/admin')
    logger.info('audit enabled: methods=%s retention=%s days',
                sorted(config.AUDITED_METHODS), config.RETENTION_DAYS)
