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

- увидеть статус API, состояние SQLite dataset, количество сообщений и маршрутов;
- просмотреть dashboard-сводку по сообщениям, приоритетам и источникам;
- отфильтровать очередь по типу, приоритету, аэропорту, источнику, фазе рейса и текстовому поиску;
- выбрать сообщение из плотной operational-таблицы;
- создать сообщение через `POST`;
- обновить сообщение через `PUT`;
- проверить JSON `payload` и `context` до отправки;
- построить маршрут выбранного сообщения;
- увидеть канал маршрутизации, `route_key`, TTL, получателей и человекочитаемые причины маршрута;
- посмотреть последние сохраненные решения маршрутизации;
- пересобрать базу синтетики вместе с real-data после подтверждения;
- импортировать реальные FAA/AWC данные.

UI реализован как single-page static console без React/Vite/build step. Визуальная концепция - строгая aviation operations console для дипломной демонстрации, а не маркетинговая страница. Интерфейс использует существующие `/api/v1/aviation/*` endpoints и не добавляет новые публичные API.

Проверка после реализации нового UI 11 июня 2026 года:

- `python -m py_compile app\core\main.py app\core\config.py app\api\routes.py app\api\schemas.py app\aviation\models.py app\aviation\routing.py app\aviation\repository.py app\aviation\generator.py app\aviation\real_data.py` -> OK;
- `python -m unittest discover -s tests -v` -> `Ran 29 tests`, `OK`;
- HTTP smoke: `GET /`, `GET /api/v1/aviation/overview`, `GET /api/v1/aviation/messages?limit=20`, `GET /api/v1/aviation/routes` -> 200;
- Chrome headless smoke на временной базе: загрузка UI, фильтр `MVT`, выбор сообщения, построение маршрута, invalid JSON, создание и обновление сообщения -> OK;
- responsive smoke: `1440x900`, `768x1024`, `390x844` -> обязательные кнопки видимы, body-level horizontal overflow не найден, console errors не обнаружены.

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
- дополнение частичных live AWC ответов snapshot-данными;
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

   Если live AWC возвращает только часть ожидаемого набора METAR/TAF, importer дополняет результат bundled snapshot-данными и дедуплицирует сообщения по `message_id`. Это снижает риск нестабильных тестов и демонстрации.

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

## 17. Оценка полноты текущей документации

Текущая документация достаточно хорошо описывает backend и доменную часть проекта: назначение системы, архитектуру, авиационную модель данных, генерацию синтетики, импорт публичных FAA/AWC данных, SQLite-хранилище, правила маршрутизации, REST API, запуск, тестирование и известные ограничения.

Для понимания проекта как инженерной системы документации достаточно: по ней можно восстановить, какие модули существуют, как данные проходят через систему, какие endpoints доступны и какие сценарии уже проверены тестами.

Для разработки нового качественного пользовательского интерфейса документации пока недостаточно. В ней есть описание текущего простого UI, но нет полноценного UX/UI-ТЗ:

- не описаны целевые пользователи и демонстрационный сценарий для дипломной защиты;
- не зафиксированы структура экранов, приоритеты информации и пользовательские сценарии;
- не заданы требования к визуальной системе, адаптивности, доступности и состояниям ошибок;
- не описаны критерии приемки интерфейса и обязательные UI smoke-тесты;
- не сформулированы ограничения по стеку и использованию внешних design/MCP-инструментов.

Вывод: текущая документация хорошо документирует проектный и backend-контекст, но ее нужно дополнить отдельным ТЗ на интерфейс. Это ТЗ приведено ниже и должно использоваться как входной контекст для следующей нейросети или следующего этапа разработки.

## 18. Техническое задание на разработку нового интерфейса

Дата подготовки ТЗ: 11 июня 2026 года.

### 18.1 Цель задачи

Разработать новый пользовательский интерфейс для дипломного проекта `ESB Aviation` - демонстрационной корпоративной шины данных для контекстно-зависимой маршрутизации авиаоперационных сообщений.

Интерфейс должен выглядеть как профессиональная operational-консоль для авиационного интеграционного контура, а не как лендинг или учебный макет. Главная задача UI - быстро показать комиссии и пользователю, что система принимает авиационные сообщения, хранит их, фильтрует, строит маршрут доставки по бизнес-правилам и объясняет причины маршрутизации.

Новый UI должен:

- демонстрировать ценность проекта в первые 10-15 секунд после открытия страницы;
- делать понятной связь между сообщением, контекстом и итоговым маршрутом;
- позволять выполнить основные операции без Swagger;
- сохранять работоспособность без PostgreSQL и без live-сети AWC за счет SQLite и snapshot fallback;
- выглядеть современно, аккуратно и достаточно строго для дипломной защиты.

### 18.2 Контекст проекта

Проект - FastAPI-приложение с авиационным контуром поверх исходной плагинной КШД.

Основная точка запуска:

```text
app.core.main:app
```

Корневой маршрут:

```text
GET /
```

Он отдает HTML из:

```text
app/templates/index.html
```

Основной API-префикс:

```text
/api/v1
```

Авиационный контур работает через SQLite:

```text
resources/synthetic_aviation_messages.db
```

PostgreSQL используется исходной КШД для request logging, но авиационные endpoints и интерфейс не должны зависеть от доступности PostgreSQL.

Плагинная часть проекта сохраняется:

- `PluginManager` загружает плагины из `app/plugins`;
- конфигурация находится в `app/plugins/plugins_config.json`;
- есть демонстрационные плагины `system_a` и `system_b`;
- административные plugin endpoints защищены JWT и ролью `ADMIN`;
- авиационные demo endpoints сейчас не требуют JWT, чтобы дипломную демонстрацию можно было провести локально и быстро.

### 18.3 Доменная модель

Основная сущность - `AviationMessage`.

Поля сообщения:

- `message_id` - уникальный идентификатор;
- `message_type` - тип сообщения;
- `priority` - приоритет;
- `origin_airport` - ICAO-код аэропорта отправления или станции;
- `destination_airport` - ICAO-код аэропорта назначения или станции;
- `flight_number` - номер рейса или служебный идентификатор;
- `operator` - оператор или источник;
- `received_at` - время получения;
- `payload` - полезная нагрузка;
- `aircraft_registration` - регистрационный номер ВС;
- `context` - контекст маршрутизации.

Поддерживаемые типы сообщений:

```text
FPL, DLA, CNL, CHG, MVT, LDM, CPM, NOTAM, METAR, TAF, SIGMET, SLOT, PAXLST, BAG, MAINT, TECHLOG, SECURITY, AFTN
```

Поддерживаемые приоритеты:

```text
NORMAL, URGENT, CRITICAL, DISTRESS
```

Важные поля `payload`:

- `event`;
- `raw_message`;
- `flight_category`;
- `visibility`;
- `wind_speed`;
- `cargo_kg`;
- `passengers`;
- `aircraft_type`;
- другие демонстрационные поля.

Важные поля `context`:

- `flight_phase`: `preflight`, `turnaround`, `in_flight`, `postflight`;
- `weather_severity`: число от 0 до 5;
- `regulatory_zone`: например `RF`, `EU`, `ICAO`;
- `source_system`: например `AODB`, `DCS`, `MRO`, `AFTN`, `MET`, `FAA`, `AWC`;
- `data_kind`;
- `schema_version`.

### 18.4 Маршрутизация, которую должен объяснять UI

Маршрутизатор `ContextAwareAviationRouter` принимает `AviationMessage` и возвращает `RoutingDecision`.

Поля решения:

- `message_id`;
- `route_key`;
- `destinations`;
- `priority_channel`;
- `reasons`;
- `ttl_seconds`.

UI должен визуально объяснять:

- какой канал выбран: `standard`, `urgent`, `critical`, `distress`;
- какие получатели добавлены;
- какие правила сработали;
- почему изменился TTL;
- какие факторы повлияли на эскалацию: priority, severe weather, distress, security/safety event, hub airport, flight phase, regulatory zone.

Базовая логика:

- неизвестные типы идут в `message_triage`;
- хабы `UUDD`, `UUEE`, `ULLI`, `URSS` добавляют `hub_control_<icao>`;
- `turnaround` добавляет ground/turnaround получателей;
- `in_flight` добавляет flight watch/dispatch;
- safety события добавляют safety/emergency routing;
- security события добавляют security routing;
- `weather_severity >= 3` добавляет safety и operations;
- `weather_severity >= 4` повышает канал до `urgent`;
- `DISTRESS` всегда дает канал `distress` и TTL 60 секунд.

### 18.5 Доступные API для интерфейса

Интерфейс должен использовать существующие endpoints без изменения backend-контракта:

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/api/v1/aviation/overview` | сводка по базе |
| `GET` | `/api/v1/aviation/messages` | список сообщений с фильтрами |
| `GET` | `/api/v1/aviation/messages/{message_id}` | детальная загрузка сообщения |
| `POST` | `/api/v1/aviation/messages` | создание сообщения |
| `PUT` | `/api/v1/aviation/messages/{message_id}` | обновление сообщения |
| `POST` | `/api/v1/aviation/messages/{message_id}/route` | построить и сохранить маршрут |
| `POST` | `/api/v1/aviation/route` | построить маршрут по телу без сохранения |
| `GET` | `/api/v1/aviation/routes` | список сохраненных решений |
| `POST` | `/api/v1/aviation/synthetic/generate` | пересобрать синтетическую базу |
| `POST` | `/api/v1/aviation/real/import` | импортировать FAA/AWC данные |

Поддерживаемые query-параметры для списка сообщений:

- `limit`;
- `offset`;
- `message_type`;
- `priority`;
- `airport`.

### 18.6 Целевые пользователи

Основные пользователи для дипломной демонстрации:

1. Член комиссии или преподаватель.
   Должен быстро понять идею: ESB принимает сообщения, нормализует их и маршрутизирует по контексту.

2. Оператор авиационного интеграционного контура.
   Должен видеть очередь сообщений, приоритеты, источники, аэропорты, фазу рейса и состояние маршрутизации.

3. Интегратор/разработчик.
   Должен видеть JSON payload/context, route key, причины маршрутизации и API-совместимое представление данных.

Интерфейс не является сертифицированной авиационной operational-системой. Нужно явно сохранять демонстрационный характер данных и не создавать впечатление, что UI предназначен для реального управления полетами.

### 18.7 Рекомендуемый подход к инструментам дизайна

Оптимальный выбор для текущего проекта:

- использовать `UI UX Pro Max skill` как дизайн-справочник и checklist для палитры, типографики, accessibility, dashboard-паттернов и UX-состояний;
- не делать `Magic MCP by 21st.dev` обязательной runtime-зависимостью проекта;
- при наличии установленного Magic MCP можно использовать его только как design-time генератор вариантов компонентов, затем адаптировать результат вручную под текущий стек;
- не переводить проект на React/Next/Vite только ради UI, если это не требуется отдельно.

Обоснование:

- текущий проект уже обслуживает UI как один `app/templates/index.html`;
- для дипломной защиты важнее надежный локальный запуск, понятный код и отсутствие лишних внешних зависимостей;
- glassmorphism и декоративные анимации допустимы только точечно, если они не ухудшают читаемость operational-данных;
- авиационная operational-консоль должна быть строгой, контрастной, сканируемой и предсказуемой.

### 18.8 Общая UX-концепция

Первый экран должен быть рабочей панелью, а не приветственным лендингом.

Рекомендуемая структура:

```text
Header / system bar
  - ESB Aviation
  - статус API
  - статус SQLite dataset
  - короткий режим: Demo / Offline snapshot available

Main workspace
  - левая зона: фильтры и действия с данными
  - центральная зона: очередь сообщений / таблица
  - правая зона: выбранное сообщение и результат маршрутизации

Lower/secondary area
  - последние routing decisions
  - распределение по типам, приоритетам и источникам
```

На desktop допустимы 3 рабочие колонки. На tablet - 2 колонки. На mobile - последовательное расположение секций без горизонтального скролла.

### 18.9 Обязательные экраны и блоки

#### 18.9.1 Верхняя системная панель

Должна показывать:

- название `ESB Aviation`;
- краткое описание: `Контекстная маршрутизация авиаоперационных сообщений`;
- индикатор доступности API;
- количество сообщений и построенных маршрутов;
- время последнего обновления UI;
- кнопку обновления данных.

#### 18.9.2 Dashboard-сводка

Обязательные метрики:

- всего сообщений;
- построенных маршрутов;
- количество типов сообщений;
- количество источников;
- распределение по priority;
- распределение по source_system.

Желательно добавить компактные визуализации без тяжелой chart-библиотеки:

- horizontal bars для priority;
- compact bars для message types;
- chips для source systems.

#### 18.9.3 Панель фильтров

Фильтры:

- тип сообщения;
- приоритет;
- аэропорт;
- источник `source_system` как client-side фильтр, если backend не поддерживает отдельный query-параметр;
- фаза рейса как client-side фильтр;
- текстовый поиск по `message_id`, `flight_number`, `operator`, ICAO-кодам.

Фильтры должны быть быстрыми и понятными. Ввод аэропорта надо автоматически приводить к верхнему регистру.

#### 18.9.4 Очередь сообщений

Список сообщений должен быть не набором больших карточек, а сканируемой таблицей или плотной list-view.

Минимальные колонки/поля:

- priority/channel indicator;
- type;
- flight number;
- origin -> destination;
- operator/source;
- received_at;
- краткий event;
- признак routed/unrouted, если решение уже есть в `/aviation/routes`.

Выбранная строка должна быть визуально выделена.

#### 18.9.5 Детали сообщения

Правая панель или отдельная секция должна показывать выбранное сообщение:

- основные поля в человекочитаемом виде;
- `payload` в форматированном JSON;
- `context` в форматированном JSON;
- кнопку `Построить маршрут`;
- кнопку `Сохранить изменения`;
- кнопку `Создать копию/demo message`, если она не усложняет UX.

JSON-поля должны валидироваться до отправки запроса. При ошибке JSON UI должен показать конкретное поле и не отправлять запрос.

#### 18.9.6 Результат маршрутизации

После построения маршрута UI должен показать:

- `priority_channel` как заметный статус;
- `route_key`;
- `ttl_seconds` в секундах и человекочитаемо;
- список `destinations` как chips;
- список `reasons` как объяснение правил;
- отметку, что решение сохранено в `aviation_routing_decisions`.

Для дипломной защиты особенно важно визуально показать "почему именно такой маршрут". Поэтому `reasons` должны быть не только JSON-массивом, но и readable-объяснением:

- `type:MVT` -> маршрут по типу MVT;
- `hub_airport:UUDD` -> добавлен контроль хаба UUDD;
- `phase:turnaround` -> добавлены ground handling и turnaround control;
- `weather_severity:4` -> погодная эскалация;
- `priority:distress` -> аварийная эскалация.

#### 18.9.7 Управление данными

Должны быть доступны действия:

- `Сгенерировать синтетику + real-data`;
- `Импортировать FAA/AWC`;
- `Обновить`;
- создание сообщения;
- обновление сообщения.

Для `synthetic/generate` нужно подтверждение, потому что endpoint очищает текущие сообщения и решения маршрутизации через `replace_messages`.

После генерации или импорта UI должен показывать:

- сколько сообщений вставлено;
- использован ли fallback snapshot;
- что список и метрики обновлены.

### 18.10 Визуальный стиль

Рекомендуемый стиль: aviation operations dashboard.

Характер:

- строгий;
- технический;
- современный;
- плотный, но не перегруженный;
- без маркетингового hero-блока;
- без декоративных градиентных фонов, которые мешают чтению.

Палитра:

- фон: светлый нейтральный серо-голубой;
- панели: белые или почти белые;
- основной текст: темный slate/ink;
- вторичный текст: нейтральный серый;
- основной акцент: глубокий aviation blue/teal;
- success: зеленый;
- warning/urgent: янтарный;
- critical/distress: красный;
- informational: синий.

Не использовать интерфейс, доминирующий одной фиолетовой, песочной, коричневой или темно-синей гаммой.

Типографика:

- системный стек или Inter/Segoe UI, если Inter доступен;
- без отрицательного letter-spacing;
- не масштабировать шрифты через viewport width;
- крупный шрифт использовать только для ключевых метрик и заголовка системы;
- таблицы, панели и формы должны иметь компактную, читаемую типографику.

Компоненты:

- радиус карточек и controls не больше 8px;
- стабильные размеры кнопок и input;
- понятные focus states;
- badges/chips для priority, source, destinations;
- status banners для ошибок и успешных действий;
- skeleton/loading states для загрузки данных.

Анимации:

- допустимы мягкие hover/focus transitions до 150-200 ms;
- не использовать тяжелые decorative animations;
- учитывать `prefers-reduced-motion`.

### 18.11 Доступность и UX-качество

Обязательные требования:

- все поля форм должны иметь label;
- все интерактивные элементы доступны с клавиатуры;
- видимый focus state;
- сообщения статуса должны попадать в `aria-live`;
- цвет не должен быть единственным способом передать priority;
- контраст текста и фона не ниже WCAG AA;
- кнопки должны иметь понятный текст;
- ошибки JSON и API должны быть описаны человеческим языком;
- интерфейс не должен иметь горизонтальный скролл на мобильной ширине;
- динамический текст не должен перекрывать соседние элементы.

### 18.12 Безопасность frontend-кода

Текущий UI рендерит данные через `innerHTML`. Новый UI обязан экранировать динамические значения из API перед вставкой в HTML.

Требования:

- не вставлять raw `payload`, `context`, `route_key`, `operator`, `flight_number` и другие данные через небезопасный `innerHTML` без escaping;
- не использовать `eval`;
- не хранить JWT или секреты в localStorage для aviation demo;
- не добавлять внешние скрипты без необходимости;
- любые ошибки API показывать без раскрытия лишних stack trace.

### 18.13 Нефункциональные требования

Производительность:

- первая загрузка должна быть быстрой на локальном `127.0.0.1`;
- список сообщений загружать ограниченно: по умолчанию 80-100 записей;
- фильтры с текстовым вводом debounce 150-300 ms;
- большие JSON-блоки ограничивать по высоте и делать прокручиваемыми;
- не перерисовывать весь UI без необходимости при выборе строки.

Надежность:

- если API недоступен, показать понятное состояние и кнопку retry;
- если база пустая, предложить сгенерировать dataset;
- если live AWC недоступен, не считать это ошибкой UI: backend использует snapshot fallback;
- если сообщение удалено или не найдено, показать 404-состояние и сбросить выбор.

Совместимость:

- Chrome/Edge последних версий;
- desktop от 1280px;
- tablet около 768px;
- mobile около 390px.

### 18.14 Ограничения реализации

Для следующего этапа разработки интерфейса предпочтительно:

- сохранить текущую модель single-page static UI в `app/templates/index.html`;
- не добавлять frontend build system без отдельного решения;
- не менять backend API без необходимости;
- не ломать существующие тесты;
- не требовать PostgreSQL для демонстрации aviation UI;
- не требовать live-доступ к AWC для успешной демонстрации;
- сохранить русский язык интерфейса, но ключевые авиационные коды и технические поля оставлять на английском.

Если будет принято решение использовать внешний UI-инструмент:

- результат должен быть адаптирован под существующий FastAPI/static HTML стек;
- внешняя генерация компонентов не должна стать обязательным условием запуска проекта;
- визуальные эффекты не должны ухудшать читаемость данных.

### 18.15 Основные пользовательские сценарии

Сценарий 1. Быстрая демонстрация системы:

1. Открыть `http://127.0.0.1:8000/`.
2. Увидеть метрики, список сообщений и статус API.
3. Выбрать сообщение `MVT`, `METAR`, `SIGMET` или `SECURITY`.
4. Нажать `Построить маршрут`.
5. Показать `priority_channel`, `destinations`, `reasons`, `ttl_seconds`.
6. Объяснить, какие правила маршрутизации сработали.

Сценарий 2. Погодная эскалация:

1. Отфильтровать `METAR`, `TAF` или `SIGMET`.
2. Выбрать сообщение с `weather_severity >= 3`.
3. Построить маршрут.
4. Показать, что weather context добавляет `meteorology`, `flight_dispatch`, `safety_control`.
5. При `weather_severity >= 4` показать канал `urgent`.

Сценарий 3. Аварийное сообщение:

1. Найти или создать сообщение с `priority = DISTRESS` и `payload.event = emergency`.
2. Построить маршрут.
3. Показать канал `distress`, TTL 60 секунд и получателей `emergency_response`, `safety_control`, `operations_supervisor`, `priority_queue`.

Сценарий 4. Создание и обновление сообщения:

1. Заполнить форму сообщения.
2. Проверить JSON в `payload` и `context`.
3. Создать сообщение через `POST`.
4. Изменить priority или event.
5. Обновить через `PUT`.
6. Построить новый маршрут и сравнить результат.

Сценарий 5. Пересборка демонстрационной базы:

1. Нажать `Сгенерировать синтетику + real-data`.
2. Подтвердить действие.
3. Дождаться результата.
4. Убедиться, что метрики, список сообщений и decisions обновлены.

### 18.16 План тестирования интерфейса

После реализации нового UI обязательно выполнить backend-тесты:

```bash
python -m unittest discover -s tests -v
```

Проверить синтаксис ключевых файлов:

```bash
python -m py_compile app\core\main.py app\api\routes.py app\api\schemas.py app\aviation\models.py app\aviation\routing.py app\aviation\repository.py app\aviation\generator.py app\aviation\real_data.py
```

Запустить сервер:

```bash
python -m uvicorn app.core.main:app --host 127.0.0.1 --port 8000
```

Проверить HTTP smoke-сценарии:

- `GET /` возвращает 200;
- `GET /api/v1/aviation/overview` возвращает 200;
- `GET /api/v1/aviation/messages?limit=20` возвращает 200;
- `POST /api/v1/aviation/messages` возвращает 201 на валидном теле;
- `PUT /api/v1/aviation/messages/{message_id}` возвращает 200;
- `POST /api/v1/aviation/messages/{message_id}/route` возвращает 200;
- `GET /api/v1/aviation/routes` возвращает 200.

Проверить UI в браузере:

- начальная загрузка без console errors;
- корректная отрисовка dashboard;
- фильтрация по type/priority/airport;
- выбор сообщения;
- создание сообщения;
- обновление сообщения;
- построение маршрута;
- отображение saved routing decisions;
- обработка invalid JSON;
- обработка пустой базы;
- подтверждение перед пересборкой базы;
- responsive layout на desktop/tablet/mobile;
- keyboard navigation и focus states.

### 18.17 Критерии приемки

Интерфейс считается готовым, если:

- все существующие unit/API-тесты проходят;
- страница `/` открывается локально и не требует отдельной frontend-сборки;
- пользователь может выполнить основные сценарии без Swagger;
- UI показывает не только JSON, но и понятное объяснение маршрутизации;
- все aviation endpoints, используемые интерфейсом, обрабатывают loading/success/error states;
- при недоступности PostgreSQL aviation UI остается работоспособным;
- при недоступности live AWC демонстрация не ломается благодаря snapshot fallback;
- нет небезопасного вывода API-данных без escaping;
- интерфейс адаптивен и не ломается на мобильной ширине;
- визуальный стиль соответствует строгой aviation operations console;
- документация после реализации обновлена: описаны изменения UI и результаты проверки.

### 18.18 Итоговое направление дизайна

Нужно проектировать не "красивую страницу", а рабочую диспетчерскую консоль для объяснимой маршрутизации сообщений.

Лучшее решение для дипломного проекта:

- оставить надежный FastAPI + static HTML/CSS/JS подход;
- использовать профессиональные UI/UX guidelines как справочник;
- применить современный, но сдержанный dashboard-дизайн;
- сделать главный акцент на объяснимости маршрута, статусах, фильтрации и демонстрационных сценариях;
- избегать тяжелых декоративных эффектов и зависимостей, которые могут сорвать локальную защиту.
