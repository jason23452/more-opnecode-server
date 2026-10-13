# 11: 同步本機終端尺寸至遠端 TUI

**What to build:** 讓容器內的 OpenCode TUI 使用本機終端實際尺寸，並在使用者調整視窗後同步更新，避免 TUI 只佔固定大小區塊或把終端查詢回覆顯示成 prompt。

**Blocked by:** 09: 透過容器 Tunnel 直接連入遠端 TUI.

**Status:** ready-for-agent

- [ ] CLI 連線時取得本機終端的 columns/rows，透過與鍵盤輸入分離的 WebSocket 控制訊息傳送初始尺寸。
- [ ] 本機終端尺寸改變時，CLI 傳送新的 columns/rows；支援 Windows PowerShell/Windows Terminal 與 macOS/Linux 終端。
- [ ] 容器 relay 將尺寸更新套用至 OpenCode PTY 並通知 TUI 重排版；不將 resize 控制訊息或終端能力查詢回覆當作一般按鍵文字。
- [ ] 使用已知尺寸的 PTY 驗證遠端程序讀到正確列/欄數；尺寸改變後再次驗證遠端 PTY 更新。
- [ ] Windows 終端 E2E 驗證 TUI 可使用完整視窗尺寸，調整視窗後內容隨之重排，且能力查詢回覆不會出現在 prompt。
