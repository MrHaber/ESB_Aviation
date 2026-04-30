# ESB Aviation: документация проекта

## 1. Назначение

Проект представляет собой корпоративную шину данных (КШД), адаптированную для контекстно-зависимой маршрутизации авиаоперационных сообщений.

Система принимает авиационные сообщения разных типов, нормализует их в единую доменную модель, сохраняет в локальную демонстрационную базу, строит маршрут доставки по набору бизнес-правил и показывает состояние системы через простой web-интерфейс.

Основной сценарий:

1. Сгенерировать или импортировать авиаоперационные сообщения.
2. Просмотреть состав базы сообщений.
3. Выбрать сообщение.
4. Построить для него маршрут.
5. Увидеть получателей, приоритетный канал, причины маршрутизации и TTL.

## 2. Что реализовано

В проект добавлен авиационный контур поверх существующей FastAPI/Plugin архитектуры:

- доменная модель авиационного сообщения;
- синтетический генератор сообщений;
- импорт реальных публичных примеров и погодных сообщений;
- SQLite-хранилище авиационных сообщений и решений маршрутизации;
- контекстно-зависимый маршрутизатор;
- REST API для GET/POST/PUT/route операций;
- простой визуальный интерфейс;
- юнит и API-тесты.

Ключевые файлы:

- `app/aviation/models.py` - модели `AviationMessage`, `RoutingDecision`, enum-типы сообщений и приоритетов;
- `app/aviation/routing.py` - правила контекстной маршрутизации;
- `app/aviation/generator.py` - генератор синтетических авиаоперационных сообщений;
- `app/aviation/real_data.py` - импорт публичных FAA/AWC данных;
- `app/aviation/repository.py` - SQLite-репозиторий;
- `app/api/routes.py` - REST API;
- `app/api/schemas.py` - Pydantic-схемы API;
- `app/templates/index.html` - демонстрационный интерфейс;
- `scripts/generate_synthetic_aviation_db.py` - CLI-генератор базы;
- `tests/test_aviation_routing.py` - тесты доменной логики;
- `tests/test_aviation_api.py` - тесты backend API.

## 3. Архитектура

Логическая схема:

```text
Web UI
  |
  v
FastAPI routes
  |
  +--> AviationMessageRepository -- SQLite DB
  |
  +--> ContextAwareAviationRouter
  |
  +--> SyntheticAviationMessageGenerator
  |
  +--> RealAviationDataImporter

Existing ESB plugins
  |
  +--> system_a
  +--> system_b
```

Существующая КШД сохраняет плагинную архитектуру. Авиационный контур добавлен отдельным пакетом `app/aviation`, чтобы он мог тестироваться независимо от внешних WebSocket, HTTP-плагинов и PostgreSQL-журнала запросов.

Для демонстрационных авиационных данных используется SQLite:

```text
resources/synthetic_aviation_messages.db
```

PostgreSQL из исходного проекта по-прежнему используется для общего request logging, но авиационный контур не зависит от него. Это важно для локальной демонстрации: даже если PostgreSQL недоступен, авиационные ручки и интерфейс продолжают работать.

## 4. Доменная модель сообщения

Единая модель сообщения описана в `AviationMessage`.

Основные поля:

| Поле | Назначение |
|---|---|
| `message_id` | уникальный идентификатор сообщения |
| `message_type` | тип авиационного сообщения: `FPL`, `METAR`, `TAF`, `MVT` и т.д. |
| `priority` | приоритет: `NORMAL`, `URGENT`, `CRITICAL`, `DISTRESS` |
| `origin_airport` | ICAO-код аэропорта отправления или станции |
| `destination_airport` | ICAO-код аэропорта назначения или станции |
| `flight_number` | номер рейса или служебный идентификатор |
| `operator` | оператор/источник |
| `received_at` | время получения |
| `payload` | полезная нагрузка сообщения |
| `aircraft_registration` | регистрационный номер ВС, если применимо |
| `context` | контекст маршрутизации: фаза рейса, погодная опасность, источник, регуляторная зона |

Пример:

```json
{
  "message_id": "demo-001",
  "message_type": "MVT",
  "priority": "URGENT",
  "origin_airport": "UUDD",
  "destination_airport": "ULLI",
  "flight_number": "ESB777",
  "operator": "ESB Air",
  "received_at": "2026-04-26T10:00:00Z",
  "payload": {
    "event": "delay"
  },
  "aircraft_registration": "RA-77777",
  "context": {
    "flight_phase": "turnaround",
    "weather_severity": 0,
    "source_system": "SMOKE"
  }
}
```

## 5. Какие сообщения эмулируются

Генератор воспроизводит набор авиаоперационных сообщений, типичных для аэропортовой, диспетчерской, грузовой, пассажирской, метеорологической и инженерной эксплуатации.

| Тип | Назначение | Эмулируемый смысл |
|---|---|---|
| `FPL` | flight plan | план полета, маршрут, связь с ATC |
| `DLA` | delay | задержка рейса |
| `CNL` | cancellation | отмена рейса/плана |
| `CHG` | change | изменение плана или параметров рейса |
| `MVT` | movement | движение рейса: off-block, airborne, arrival, delay |
| `LDM` | load message | загрузка, пассажиры, масса груза |
| `CPM` | container/pallet message | грузовые контейнеры, cargo handling |
| `NOTAM` | notice to airmen | эксплуатационное уведомление |
| `METAR` | meteorological aerodrome report | фактическая погода |
| `TAF` | terminal aerodrome forecast | прогноз по аэродрому |
| `SIGMET` | significant meteorological information | опасные метеоявления |
| `SLOT` | slot coordination | слот, координация вылета/прилета |
| `PAXLST` | passenger list | пассажирский список |
| `BAG` | baggage | багажная сверка |
| `MAINT` | maintenance | инженерно-техническое обслуживание |
| `TECHLOG` | technical log | технический журнал ВС |
| `SECURITY` | security event | события безопасности |
| `AFTN` | aeronautical fixed telecommunication network | универсальное авиационное сообщение/триаж |

События внутри `payload` также эмулируются:

- `operational_update`;
- `delay`;
- `off_block`;
- `airborne`;
- `arrival`;
- `load_update`;
- `weather_update`;
- `mel_item`;
- `technical_delay`;
- `service_release`;
- `security_alert`;
- `emergency`.

Фазы рейса в `context.flight_phase`:

- `preflight`;
- `turnaround`;
- `in_flight`;
- `postflight`.

Погодная опасность в `context.weather_severity` задается шкалой от 0 до 5.

## 6. Реальные публичные данные

Проект использует два класса публичных данных:

1. FAA examples - официальные примеры ICAO-сообщений:
   - `FPL`;
   - `CNL`;
   - `CHG`.

2. NOAA Aviation Weather Center Data API:
   - live `METAR`;
   - live `TAF`.

Файл `app/aviation/real_data.py` сначала пытается получить live weather-данные через API Aviation Weather Center. Если сеть недоступна, используется сохраненный snapshot:

```text
resources/awc_weather_snapshot_2026_04_26.json
```

Snapshot содержит реальные METAR/TAF, полученные 26 апреля 2026 года для набора аэропортов:

- `UUDD` - Moscow/Domodedovo;
- `UUEE` - Moscow/Sheremetyevo;
- `ULLI` - St Petersburg/Pulkovo;
- `URSS` - Sochi;
- `EDDF` - Frankfurt;
- `LEMD` - Madrid.

Используемые источники:

- NOAA Aviation Weather Center Data API: https://aviationweather.gov/data/api/
- FAA ICAO message examples: https://www.faa.gov/about/office_org/headquarters_offices/ato/service_units/air_traffic_services/flight_plan_filing/guidance/reference_guide/message_ack_rej/message_examples
- FAA NOTAM reference: https://www.faa.gov/air_traffic/flight_info/aeronav/notams/

## 7. Синтетическая база данных

Основная демонстрационная база:

```text
resources/synthetic_aviation_messages.db
```

Таблицы:

### `aviation_messages`

Хранит нормализованные авиационные сообщения.

Основные колонки:

- `message_id`;
- `message_type`;
- `priority`;
- `origin_airport`;
- `destination_airport`;
- `flight_number`;
- `operator`;
- `received_at`;
- `aircraft_registration`;
- `payload`;
- `context`.

### `aviation_routing_decisions`

Хранит построенные решения маршрутизации.

Основные колонки:

- `message_id`;
- `route_key`;
- `destinations`;
- `priority_channel`;
- `reasons`;
- `ttl_seconds`;
- `created_at`.

Пересобрать базу можно командой:

```bash
python scripts/generate_synthetic_aviation_db.py --count 320 --seed 42 --include-real-data
```

Параметры:

- `--count` - итоговое количество сообщений;
- `--seed` - seed для воспроизводимости;
- `--db-path` - путь к SQLite-файлу;
- `--include-real-data` - включить FAA/AWC данные в общий набор.

## 8. Правила маршрутизации

Маршрутизатор реализован в `ContextAwareAviationRouter`.

На вход он получает `AviationMessage`, на выходе возвращает `RoutingDecision`.

Решение содержит:

- `message_id`;
- `route_key`;
- `destinations`;
- `priority_channel`;
- `reasons`;
- `ttl_seconds`.

Пример решения:

```json
{
  "message_id": "smoke-001",
  "route_key": "aviation.urgent.mvt.uudd.ulli",
  "destinations": [
    "airport_operations",
    "flight_dispatch",
    "ground_handling",
    "hub_control_ulli",
    "hub_control_uudd",
    "operations_supervisor",
    "priority_queue",
    "turnaround_control"
  ],
  "priority_channel": "urgent",
  "reasons": [
    "type:MVT",
    "hub_airport:UUDD",
    "hub_airport:ULLI",
    "phase:turnaround",
    "priority:urgent"
  ],
  "ttl_seconds": 300
}
```

### 8.1 Базовая маршрутизация по типу

Каждый тип сообщения имеет базовых получателей.

Примеры:

- `FPL` -> `flight_dispatch`, `atc_gateway`, `airport_operations`;
- `MVT` -> `flight_dispatch`, `airport_operations`, `ground_handling`;
- `LDM` -> `load_control`, `ground_handling`, `airport_operations`;
- `METAR`/`TAF` -> `meteorology`, `flight_dispatch`;
- `SECURITY` -> `security_control`, `airport_operations`.

Неизвестный тип отправляется в:

```text
message_triage
```

### 8.2 Контекст аэропортов-хабов

Хабы:

```text
UUDD, UUEE, ULLI, URSS
```

Если origin или destination входит в список хабов, добавляется адресат:

```text
hub_control_<icao>
```

Например:

```text
hub_control_uudd
```

### 8.3 Контекст фазы рейса

Если `flight_phase = turnaround`, добавляются:

- `ground_handling`;
- `turnaround_control`.

Если `flight_phase = in_flight`, добавляются:

- `flight_watch`;
- `flight_dispatch`.

### 8.4 Safety/security события

Safety события:

- `emergency`;
- `diversion`;
- `bird_strike`;
- `runway_incursion`.

При таких событиях добавляются:

- `safety_control`;
- `flight_dispatch`;
- `emergency_response`.

Security события:

- `security_alert`;
- `unruly_passenger`;
- `screening_match`.

Для них добавляются:

- `security_control`;
- `airport_operations`.

Тип `SECURITY` также автоматически получает security-маршрутизацию.

### 8.5 Погодный контекст

Если сообщение относится к `METAR`, `TAF`, `SIGMET` или имеет `weather_severity > 0`, добавляется:

```text
meteorology
```

Если `weather_severity >= 3`, добавляются:

- `airport_operations`;
- `flight_dispatch`;
- `safety_control`.

Если `weather_severity >= 4`, канал становится `urgent`, даже если исходный приоритет сообщения `NORMAL`.

### 8.6 Приоритеты

Поддерживаются приоритеты:

- `NORMAL`;
- `URGENT`;
- `CRITICAL`;
- `DISTRESS`.

Каналы:

| Приоритет/условие | Канал |
|---|---|
| `NORMAL` | `standard` |
| `URGENT` | `urgent` |
| `CRITICAL` | `critical` |
| `DISTRESS` | `distress` |
| `weather_severity >= 4` | `urgent` |

Для `URGENT` и `CRITICAL` добавляются:

- `operations_supervisor`;
- `priority_queue`.

Для `DISTRESS` добавляются:

- `emergency_response`;
- `operations_supervisor`;
- `safety_control`;
- `priority_queue`.

### 8.7 TTL

TTL задает срок актуальности маршрута:

| Условие | TTL |
|---|---:|
| `distress` | 60 секунд |
| `critical` или `urgent` | 300 секунд |
| `METAR`, `TAF`, `SIGMET`, `NOTAM` | 1800 секунд |
| остальные сообщения | 3600 секунд |

## 9. REST API

Базовый префикс:

```text
/api/v1
```

### 9.1 Авиационные ручки

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/aviation/synthetic/generate` | пересобрать базу синтетики |
| `POST` | `/aviation/real/import` | импортировать FAA/AWC реальные данные |
| `GET` | `/aviation/overview` | получить сводку по базе |
| `GET` | `/aviation/messages` | список сообщений |
| `GET` | `/aviation/messages/{message_id}` | одно сообщение |
| `POST` | `/aviation/messages` | создать сообщение |
| `PUT` | `/aviation/messages/{message_id}` | обновить сообщение |
| `POST` | `/aviation/route` | построить маршрут для тела запроса без сохранения сообщения |
| `POST` | `/aviation/messages/{message_id}/route` | построить и сохранить маршрут для сообщения из БД |
| `GET` | `/aviation/routes` | список сохраненных решений маршрутизации |

### 9.2 Примеры запросов

Получить сводку:

```bash
curl http://127.0.0.1:8000/api/v1/aviation/overview
```

Получить первые сообщения:

```bash
curl "http://127.0.0.1:8000/api/v1/aviation/messages?limit=20"
```

Фильтр по типу:

```bash
curl "http://127.0.0.1:8000/api/v1/aviation/messages?message_type=METAR"
```

Фильтр по аэропорту:

```bash
curl "http://127.0.0.1:8000/api/v1/aviation/messages?airport=UUDD"
```

Создать сообщение:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/aviation/messages ^
  -H "Content-Type: application/json" ^
  -d "{\"message_id\":\"demo-001\",\"message_type\":\"MVT\",\"priority\":\"NORMAL\",\"origin_airport\":\"UUDD\",\"destination_airport\":\"ULLI\",\"flight_number\":\"ESB900\",\"operator\":\"ESB Air\",\"received_at\":\"2026-04-26T10:00:00Z\",\"payload\":{\"event\":\"operational_update\"},\"aircraft_registration\":\"RA-90000\",\"context\":{\"flight_phase\":\"turnaround\",\"weather_severity\":0,\"source_system\":\"DEMO\"}}"
```

Обновить сообщение:

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/aviation/messages/demo-001 ^
  -H "Content-Type: application/json" ^
  -d "{\"message_id\":\"demo-001\",\"message_type\":\"MVT\",\"priority\":\"URGENT\",\"origin_airport\":\"UUDD\",\"destination_airport\":\"ULLI\",\"flight_number\":\"ESB900\",\"operator\":\"ESB Air\",\"received_at\":\"2026-04-26T10:00:00Z\",\"payload\":{\"event\":\"delay\"},\"aircraft_registration\":\"RA-90000\",\"context\":{\"flight_phase\":\"turnaround\",\"weather_severity\":0,\"source_system\":\"DEMO\"}}"
```

Построить маршрут:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/aviation/messages/demo-001/route
```

## 10. Визуальный интерфейс

Интерфейс расположен в:

```text
app/templates/index.html
```

После запуска сервера доступен по адресу:

```text
http://127.0.0.1:8000/
```

Что можно сделать через UI:

- увидеть общее количество сообщений;
- увидеть количество построенных маршрутов;
- увидеть количество типов и источников;
- отфильтровать сообщения по типу, приоритету и аэропорту;
- выбрать сообщение из списка;
- создать сообщение через POST;
- обновить сообщение через PUT;
- построить маршрут выбранного сообщения;
- посмотреть последние сохраненные решения маршрутизации;
- пересобрать базу синтетики вместе с real-data;
- импортировать реальные FAA/AWC данные.

UI специально сделан простым: это демонстрационная operational-панель, а не маркетинговая страница.

## 11. Запуск

Установить зависимости:

```bash
python -m pip install -r requirements.txt
```

Если окружение минимальное, могут понадобиться отдельные зависимости:

```bash
python -m pip install fastapi uvicorn pydantic-settings python-jose python-multipart loguru apscheduler psycopg prometheus-client prometheus-fastapi-instrumentator aiohttp websockets xmltodict ldap3
```

Сгенерировать базу:

```bash
python scripts/generate_synthetic_aviation_db.py --count 320 --seed 42 --include-real-data
```

Запустить backend:

```bash
python -m uvicorn app.core.main:app --host 127.0.0.1 --port 8000
```

Или через существующий файл:

```bash
python run.py
```

Открыть интерфейс:

```text
http://127.0.0.1:8000/
```

Swagger/OpenAPI:

```text
http://127.0.0.1:8000/docs
```

## 12. Тестирование

Запуск всех тестов:

```bash
python -m unittest discover -s tests -v
```

Что покрыто тестами:

- маршрутизация turnaround/load сообщений;
- escalation для `DISTRESS`;
- escalation для тяжелой погоды;
- fallback неизвестного типа в `message_triage`;
- детерминированность генератора;
- включение real public data в генератор;
- импорт FAA/AWC snapshot;
- SQLite persistence и фильтрация;
- сохранение решений маршрутизации;
- обновление сообщений;
- API GET/POST/PUT/route handlers;
- API генерация синтетики и импорт реальных данных.

На последней проверке:

```text
Ran 11 tests
OK
```

Также выполнялась синтаксическая проверка:

```bash
python -m py_compile app\aviation\real_data.py app\aviation\generator.py app\aviation\repository.py app\api\routes.py app\api\schemas.py app\core\main.py app\prometheus\middleware.py app\prometheus\logger.py tests\test_aviation_api.py tests\test_aviation_routing.py scripts\generate_synthetic_aviation_db.py
```

## 13. Что сейчас работает

Работает:

- генерация синтетических сообщений;
- импорт публичных FAA/AWC данных;
- offline fallback для METAR/TAF snapshot;
- SQLite-хранение сообщений;
- SQLite-хранение решений маршрутизации;
- контекстная маршрутизация;
- REST API aviation-контура;
- POST/GET/PUT операции над сообщениями;
- построение маршрута по телу запроса;
- построение маршрута по сохраненному сообщению;
- визуальный интерфейс;
- загрузка plugin-конфигурации;
- загрузка `system_a` и `system_b` при наличии зависимостей;
- Prometheus/FastAPI instrumentation.

Проверенные HTTP-сценарии:

- `GET /` -> 200;
- `GET /api/v1/aviation/overview` -> 200;
- `POST /api/v1/aviation/messages` -> 201;
- `PUT /api/v1/aviation/messages/{message_id}` -> 200;
- `GET /api/v1/aviation/messages/{message_id}` -> 200;
- `POST /api/v1/aviation/messages/{message_id}/route` -> 200.

## 14. Известные особенности и ограничения

1. PostgreSQL request log является частью исходной КШД, но авиационный контур работает через SQLite и не зависит от PostgreSQL.

2. На Windows async `psycopg` может требовать `WindowsSelectorEventLoopPolicy`. В `app/core/main.py` startup теперь не падает полностью, если request-log база недоступна.

3. `system_b` использует WebSocket и без поднятого внешнего WebSocket-сервера может возвращать `Plugin is not running`.

4. Live AWC импорт зависит от сети. Если сети нет, используется snapshot `resources/awc_weather_snapshot_2026_04_26.json`.

5. Данные являются демонстрационными. Даже реальные METAR/TAF используются как public sample/snapshot для демонстрации маршрутизации, а не как сертифицированный operational feed.

6. UI не требует JWT для aviation demo endpoints. Плагиновые administrative endpoints исходной КШД сохраняют авторизационную модель.

## 15. Как расширять систему

Добавить новый тип сообщения:

1. Добавить тип в `AviationMessageType` в `app/aviation/models.py`.
2. Добавить базовых получателей в `BASE_DESTINATIONS` в `app/aviation/routing.py`.
3. Добавить генерацию payload в `app/aviation/generator.py`.
4. Добавить тест маршрутизации в `tests/test_aviation_routing.py`.

Добавить новое контекстное правило:

1. Добавить поле или значение в `context`/`payload`.
2. Создать новый `_apply_*_context` метод в `ContextAwareAviationRouter`.
3. Вызвать его из `route`.
4. Добавить unit test на причину (`reasons`) и получателей (`destinations`).

Добавить новый внешний источник:

1. Расширить `RealAviationDataImporter`.
2. Нормализовать входные данные в `AviationMessage`.
3. Добавить fallback snapshot при необходимости.
4. Проверить импорт тестом.

## 16. Краткое резюме

Текущая версия проекта демонстрирует рабочий aviation ESB контур:

- сообщения создаются, импортируются и сохраняются;
- реальные FAA/AWC примеры включены в набор данных;
- маршрутизация учитывает тип, аэропорты, фазу рейса, погоду, priority, safety/security и regulatory context;
- backend проверен через GET/POST/PUT/route;
- простой web-интерфейс показывает состав системы и позволяет выполнять основные операции.
