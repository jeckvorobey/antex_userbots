## Context

`asyncio.run(main())` получает SIGINT, отменяет `main()` и после завершения cleanup преобразует отмену главной задачи в `KeyboardInterrupt`. Без внешней обработки стандартный launcher печатает traceback. Scheduler cadence берётся из `swarm.orchestrator.tick_seconds`; его текущий default и production-пример равны 30 секундам.

## Goals / Non-Goals

**Goals:**

- Завершать процесс по Ctrl+C после существующего async cleanup без traceback.
- Не перехватывать ошибки runtime и не менять reconnect semantics.
- Сделать 60 секунд стандартным и production scheduler cadence.

**Non-Goals:**

- Изменение startup membership delay 30–60 секунд.
- Изменение active windows, задержек ответов или логики orchestrator.

## Decisions

- Перехватывать `KeyboardInterrupt` только вокруг `asyncio.run(main())` в `__main__`. Это сохраняет отмену внутри event loop, выполнение всех `finally` и видимость любых других исключений. Перехват `CancelledError` внутри supervisor не решает traceback `asyncio.run` и мог бы скрыть внешнюю отмену задачи.
- Вынести launcher в синхронную функцию, чтобы его поведение проверялось unit-тестом без запуска subprocess и сигналов ОС.
- Обновить default модели конфигурации, example/production TOML и README до 60 секунд. Пользовательский локальный `settings.toml` с явно заданным значением остаётся самостоятельной override-конфигурацией.

## Risks / Trade-offs

- [Повторный SIGINT во время cleanup может прервать освобождение ресурсов] → первый SIGINT проходит через стандартную отмену `asyncio.run`; поведение повторного принудительного прерывания не меняется.
- [Увеличение cadence задерживает реакцию scheduler на подходящее окно максимум на дополнительные 30 секунд] → 60 секунд является требуемым оператором балансом частоты проверок.
