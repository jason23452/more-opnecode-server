# 11: 同步本機終端尺寸至遠端 TUI

**What to build:** 讓容器內的 OpenCode TUI 使用本機終端實際尺寸，並在使用者調整視窗後同步更新，避免 TUI 只佔固定大小區塊或把終端查詢回覆顯示成 prompt。

**Blocked by:** 09: 透過容器 Tunnel 直接連入遠端 TUI.

**Status:** ready-for-human

- [x] CLI 連線時取得本機終端的 columns/rows，透過與鍵盤輸入分離的 WebSocket 控制訊息傳送初始尺寸。
- [x] 本機終端尺寸改變時，CLI 傳送新的 columns/rows；涵蓋 Windows console API 與 POSIX/macOS 終端讀取方式。
- [x] 容器 relay 驗證 resize 控制訊息，將尺寸套用至 OpenCode PTY 並通知 TUI 重排版；resize 控制訊息不會轉為按鍵輸入，Windows 終端查詢回覆仍以批次二進位鍵盤 frame 傳送。
- [x] 使用 PTY 子程序驗證初始尺寸 `100x30` 及更新後 `132x44` 可被遠端程序讀取。
- [x] 獨立 opt-in TUI-over-Tunnel E2E 在不執行上傳的全新容器驗證 `connect`；確認原先不存在的 `/workspace/project` 由 relay 建立，遠端 OpenCode PTY 依序讀到 `100x30`、`132x44`，Ctrl-C 可斷線並重新連線。
- [ ] Windows PowerShell/Windows Terminal 的實際視覺重排版仍未驗證。本工作環境為 WSL，未能在原生 Windows Terminal 確認版面與終端能力查詢回覆未出現在 prompt。

**Validation:** CLI tests 19 passed；backend tests 61 passed、3 opt-in Docker E2E skipped in the default suite；compileall、shell syntax、Linux PyInstaller build 與 executable `--help` passed。`OPENCODE_TUI_E2E=1 uv run pytest tests/test_opencode_docker_e2e.py::test_standalone_tui_tunnel_connect_propagates_size_resize_and_reconnects -q -s` passed against Windows Docker Desktop (server `29.8.2`) and a Cloudflare Tunnel, including fresh-container standalone connect, initial/live remote PTY dimensions and Ctrl-C disconnect/reconnect. The separate mixed upload/TUI E2E was reported to fail during its 96 MiB upload with Cloudflare HTTP 530 before reaching TUI; this is unrelated to resize and is not counted as resize evidence. Ticket remains `ready-for-human` solely for native Windows Terminal visual verification; POSIX PTY-over-Tunnel size, live resize, project-directory creation and reconnect have been verified.
