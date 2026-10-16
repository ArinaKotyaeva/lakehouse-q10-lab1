# Практическая №1 · Вариант 2 · TPC-H Q10

**Котяева Арина Руслановна**. MinIO → Iceberg/Lakekeeper → Trino. Слои Bronze → Silver → Gold. Дополнительный BI-инструмент — Streamlit.

## Запуск

Нужны Docker Desktop с Linux-контейнерами, около 8 ГБ памяти Docker, Docker Compose v2 и Python 3.13. На хосте достаточно стандартной библиотеки Python.

```powershell
# Из корня проекта; первый запуск скачивает образы.
docker compose up -d postgres minio lakekeeper trino
python scripts/setup.py
python scripts/run_lab.py --scale sf1 --repeats 5
docker compose up -d --build bi
# Проверка интерфейса; вывод сохранён также в results/bi_check.json
python scripts/check_bi.py
python scripts/make_report.py
```

Проверяйте код завершения каждой команды. Удобный первый этап для PowerShell: `./scripts/start.ps1`. Запуск BI после бенчмарка исключает влияние запросов графиков на измерения.

Повторный `run_lab.py` использует уже загруженные Bronze и исходные времена записи. Нельзя менять масштаб существующего проекта: для другого масштаба нужен отдельный проект Compose с собственными томами. Silver/Gold создаются с IF NOT EXISTS: это воспроизводимый запуск статического TPC-H, не инкрементальное обновление произвольных данных.

## Результаты и интерфейсы

- [Отчёт по форме преподавателя](report.md) — решения, таблицы, реальные измерения и выводы.
- [Топ-20 клиентов](results/gold_top20.csv).
- [Бенчмарк](results/benchmark.csv).

| Интерфейс | Адрес | Доступ |
|---|---|---|
| BI: Bronze и Gold | http://localhost:18088 | без авторизации, только localhost |
| Trino | http://localhost:18080 | пользователь lab, без пароля |
| Lakekeeper | http://localhost:18181 | локальный учебный каталог |
| MinIO Console | http://localhost:19001 | labadmin / lab_local_password |

## Содержимое

- `compose.yaml`, `config/` — развёртывание и настройки.
- `scripts/setup.py` — создание бакета и warehouse.
- `scripts/run_lab.py` — ELT, бенчмарк, сверка с Q10, проверки качества и снимков.
- `scripts/make_report.py` — отчёт из измерений.
- `sql/` — SQL выполненного запуска.
- `results/` — фактические CSV/JSON и SQL-журнал с query ID.
- `bi/` — Dockerfile, зависимости и приложение.

Размеры — активные файлы данных Iceberg, десятичные МБ, без метаданных и старых снимков. Время SQL — медиана пяти чередующихся запусков после прогрева. Время записи — сумма четырёх CTAS (один запуск), включая генерацию TPC-H. Это локальный учебный эксперимент, не сертифицированный TPC-H benchmark. Подробная методика и ограничения находятся в отчёте.

## Остановка и сдача

`docker compose stop` останавливает сервисы с сохранением данных. `docker compose up -d` запускает снова. Не выполняйте `down -v`, если хотите сохранить данные и снимки.

Для сдачи загрузите проект в репозиторий своей учётной записи GitHub, включая `results/` и `report.md`. Данные Docker-томов и образы в Git не загружаются: они воспроизводятся командами. Скриншоты реального интерфейса приложены: `results/bronze-ui.png` и `results/gold-ui.png`. Необязательный `scripts/screenshot.py` повторяет съёмку на Windows через установленный Edge; только для него требуется пакет Python `websockets`.
