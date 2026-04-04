# KST(한국시간) 영구 고정 가이��

> 클라우드 서버에서 봇 스케줄러가 UTC 시간대로 리셋되는 문제를 해결하는 실전 팁

## 문제 상황

AWS/GCP 등 클라우드 서버는 커널 업데이트나 재부팅 시 시간대를 **UTC(영국 런던 시간)**으로 초기화합니다.
이로 인해 파이썬 봇의 스케줄러가 KST 기준이 아닌 UTC 기준으로 동작하여, 정규장 자�� 주문이 **9시간 지연**��는 현상이 발생합니다.

### 증상

- 텔레그램 명령어에는 정상 응답하지만 스케줄 주문만 침��
- `systemctl status` 로그에 `UTC` 시간이 표시됨
- `timedatectl set-timezone Asia/Seoul` 후에도 파이썬 스케줄러가 UTC를 유지

## 해결 방법

systemd 서비스 파일에 `TZ=Asia/Seoul` 환경변수를 직접 박아서, 클라우드가 시간대를 리셋해도 봇은 무조건 KST로 동작하도록 합니다.

### 1줄 스크립트 (터미널에 통째로 복붙)

```bash
cat << 'EOF' > /etc/systemd/system/pipiosbot.service
[Unit]
Description=PIPIOS Trading Zombie Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pipios4006
Environment="TZ=Asia/Seoul"
ExecStart=/usr/bin/python3 /home/pipios4006/main.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart pipiosbot
```

> 자신의 봇 이름(`pipiosbot`)과 경로(`/home/pipios4006`)가 다르면 해당 부분만 수정하세요.

### 핵심 라인

```ini
Environment="TZ=Asia/Seoul"
```

이 한 줄이 파이썬 프로세스의 시간대를 **OS 설정과 무관하게** KST로 강제 고정합니다.

## 검증 방법

```bash
# 서비스 상태 확인
sudo systemctl status pipiosbot

# 실시간 로그 확인 (시간대가 KST인지 체크)
journalctl -u pipiosbot -f
```

로그에 `scheduled_regular_trade` 등의 스케줄 작업이 KST 기준 시간으로 표시되면 성공입니다.
