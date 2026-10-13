# 專案檔案經 Tunnel 直接上傳至容器

本機 CLI 將專案檔案直接傳至目標容器的 Tunnel ingress；管理後端只負責建立容器、提供容器專屬授權與刷新 Tunnel upload URL，不代理檔案 payload。此方式避免大型檔案佔用管理後端頻寬與記憶體，但要求容器提供受限且安全的上傳接收器，並以分塊傳輸、Tunnel URL 刷新及 staging 安裝處理請求大小限制與復原。
