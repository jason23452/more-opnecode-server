# 11: 同步本機終端尺寸至遠端 TUI

**What to build:** 讓容器內的 OpenCode TUI 使用本機終端實際尺寸，並在使用者調整視窗後同步更新，避免 TUI 只佔固定大小區塊或把終端查詢回覆顯示成 prompt。

**Blocked by:** 09: 透過容器 Tunnel 直接連入遠端 TUI.

**Status:** ready-for-human

- [x] CLI 連線時取得本機終端的 columns/rows，透過與鍵盤輸入分離的 WebSocket 控制訊息傳送初始尺寸。
- [x] 本機終端尺寸改變時，CLI 傳送新的 columns/rows；涵蓋 Windows console API 與 POSIX/macOS 終端讀取方式。
- [x] 容器 relay 驗證 resize 控制訊息，將尺寸套用至 OpenCode PTY 並通知 TUI 重排版；resize 控制訊息不會轉為按鍵輸入，Windows 終端查詢回覆仍以批次二進位鍵盤 frame 傳送。
- [x] 使用 PTY 子程序驗證初始尺寸 `100x30` 及更新後 `132x44` 可被遠端程序讀取。
- [ ] Windows 終端 E2E 尚未驗證。本工作環境為 WSL，沒有 Windows PowerShell/Windows Terminal；Docker/Cloudflare TUI E2E 能啟動 OpenCode 並送出 resize，但在後續 Ctrl-C 結束 TUI 時逾時，未完成 reconnect 驗證及視覺重排版確認。

**Validation:** CLI tests 19 passed；backend tests 61 passed、2 opt-in E2E skipped；compileall、shell syntax、PyInstaller build 與 executable `--help` passed。Docker Desktop autodetection 回報 server `29.8.2`。執行 `OPENCODE_DOCKER_E2E=1` 的 TUI E2E 時，容器建立、上傳、TUI 啟動與 resize 發送均到達，但測試在 Ctrl-C 後等待 CLI 結束 10 秒逾時，因此此 ticket 保留 `ready-for-human`，待 Windows 終端重排版及完整 TUI disconnect/reconnect E2E 驗收。
