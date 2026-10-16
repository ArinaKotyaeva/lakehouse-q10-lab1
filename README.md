# Практическая №1 · Вариант 2 · TPC-H Q10

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
