# Tests

Дата проверки: 2026-05-11.

## Команда запуска

```powershell
python -B -m unittest discover -s tests -v
```

Флаг `-B` отключает запись служебных `__pycache__` во время проверки. `pytest` и `coverage` в текущем Python-окружении не установлены, поэтому проект проверен штатным `unittest`.

## Итоговый результат

```text
Ran 29 tests in 0.994s

OK
```

Все тесты проекта прошли успешно.

## Покрытые области

| Область | Что проверено | Результат |
| --- | --- | --- |
| Aviation API | создание, список, получение, обновление, фильтрация, inline-routing, routing сохраненного сообщения, overview, 404 для отсутствующего сообщения | OK |
| Контекстная маршрутизация | turnaround LDM, DISTRESS emergency, severe weather escalation, неизвестный тип сообщения | OK |
| Генератор авиационных сообщений | детерминированность по seed, разнообразие типов, включение публичных FAA/AWC данных | OK |
| Импорт реальных данных | загрузка FAA/AWC примеров, наличие METAR и TAF сообщений | OK |
| SQLite repository | replace/list/filter/count/update, сохранение routing decision, overview | OK |
| Auth/JWT | генерация JWT по `sub`, admin role escalation, `/api/v1/auth/token`, проверка доступа к protected endpoint | OK |
| Plugins | загрузка, список, выгрузка, ошибка отсутствующего плагина, корректное определение runnable-плагина | OK |
| Transformers | CSV, XML, binary, OData success/failure | OK |
| Helpers | UUID request id, timestamp, interval/date triggers, invalid/past schedules, Moscow time conversion | OK |

## Вывод критического функционала

### Aviation API

Проверенный сценарий CRUD и routing:

```text
POST /api/v1/aviation/messages -> 201, message_id=api-001
GET /api/v1/aviation/messages -> 200, count=1
GET /api/v1/aviation/messages/api-001 -> 200, message_type=MVT
PUT /api/v1/aviation/messages/api-001 -> 200, priority=URGENT
POST /api/v1/aviation/messages/api-001/route -> 200, destinations include priority_queue
GET /api/v1/aviation/routes -> 200, count=1
GET /api/v1/aviation/overview -> 200, total_messages=1
```

Негативный сценарий:

```text
GET /api/v1/aviation/messages/missing -> 404, detail="Aviation message not found"
POST /api/v1/aviation/messages/missing/route -> 404, detail="Aviation message not found"
```

### Контекстная маршрутизация

Критические решения маршрутизатора:

```text
DISTRESS + emergency -> priority_channel=distress, ttl_seconds=60,
destinations include emergency_response, operations_supervisor, safety_control

METAR + weather_severity=4 -> priority_channel=urgent, ttl_seconds=300,
destinations include meteorology, flight_dispatch, safety_control

Unknown type CUSTOM -> destinations include message_triage,
route_key=aviation.standard.custom.zzzz.zzzz
```

### Генерация и импорт авиационных данных

```text
POST /api/v1/aviation/synthetic/generate?count=30&seed=3&include_real_data=true
-> 200, inserted=30

GET /api/v1/aviation/messages?message_type=METAR
-> 200, count >= 1

POST /api/v1/aviation/real/import
-> 200, inserted >= 15
```

### Auth/JWT

```text
create_jwt_token({"sub": "operator-1", "role": "integrator"})
-> get_current_user returns {"sub": "operator-1", "role": "integrator"}

create_jwt_token({"sub": "admin", "role": "operator"})
-> get_current_user returns role="admin"

POST /api/v1/auth/token
-> 200, token_type=bearer, access_token present

GET /api/v1/plugins with operator token
-> 403

GET /api/v1/plugins with admin token
-> 200
```

### Plugins

```text
PluginManager.load_plugin("system_a") -> {"status": "loaded"}
PluginManager.list_plugins() -> {"system_a": "stopped"}
PluginManager.is_runnable("system_a") -> False
PluginManager.unload_plugin("system_a") -> {"status": "unloaded"}

PluginManager.load_plugin("system_b") -> {"status": "loaded"}
PluginManager.is_runnable("system_b") -> True

PluginManager.load_plugin("does_not_exist")
-> {"error": "Plugin does_not_exist not found"}
```

### Transformers и helpers

```text
csv_to_json("flight,status\nESB101,ON_TIME\nESB102,DELAYED\n")
-> [{"flight": "ESB101", "status": "ON_TIME"}, {"flight": "ESB102", "status": "DELAYED"}]

xml_to_json("<flight><number>ESB101</number><status>ON_TIME</status></flight>")
-> {"flight": {"number": "ESB101", "status": "ON_TIME"}}

binary_to_json(b"\x00\x01ABC")
-> {"data": [0, 1, 65, 66, 67]}

odata_to_json(...) success
-> adds "$format=json" and returns response JSON

odata_to_json(...) request failure
-> None

create_trigger({"interval": "5 minutes"})
-> IntervalTrigger

create_trigger({"run_at": "2099-01-01T12:00:00"}, moscow_time=True)
-> DateTrigger with run_date=2099-01-01 09:00:00+00:00
```

## Изменения, найденные тестами

- Исправлена генерация JWT: теперь `create_jwt_token` принимает payload как с `username`, так и с `sub`, что соответствует `/api/v1/auth/token` и LDAP callback.
- Исправлено определение runnable-плагинов: `PluginManager.is_runnable` теперь проверяет, переопределены ли `start/stop` на уровне класса плагина, а не сравнивает bound method с методом базового класса.
