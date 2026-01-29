"""Telegram Bot 平台實作

將 Telegram Bot API 封裝為 BotAdapter Protocol 實作，
支援訊息編輯、刪除、進度通知等 Telegram 特有功能。

子模組：
- adapter: TelegramBotAdapter（實作 BotAdapter + EditableMessageAdapter + ProgressNotifier）
- handler: Webhook 事件處理
"""
