# 🎰 Lotto Bot

동행복권 자동 구매 및 Slack 알림 봇

## 기능
- 매주 자동으로 로또 5게임 구매 (자동번호)
- 구매 내역 조회 및 Slack 스레드 알림
- 잔액 확인 및 부족 시 경고
- 구매 성공/실패 여부 Slack 메시지 업데이트

---

## 설치

**1. 패키지 설치**
```bash
pip install -r requirements.txt
```

**2. 환경변수 설정**

`lotto_bot` 폴더 안에 `.env` 파일을 새로 만들고 아래 내용 입력

```
SLACK_TOKEN=여기에_슬랙_토큰
SLACK_CHANNEL=여기에_채널_ID
USER_ID=여기에_동행복권_아이디
PASSWORD="여기에_동행복권_비밀번호"
```

> ⚠️ `.env` 파일은 절대 깃허브에 올리지 마세요. `.gitignore`에 의해 자동으로 제외됩니다.

**3. 실행**
```bash
python lotto_bot.py
```

---

## Slack 알림 예시

```
⏳ 2026-02-18 로또 구매를 시작합니다.   ← 진행 중
✅ 2026-02-18 로또 구매를 완료했습니다. ← 성공
❌ 2026-02-18 로또 구매를 실패했습니다. (구매한도 초과) ← 실패
```

스레드 댓글로 구매내역, 잔액, 구매완료 메시지가 달립니다.

---

## 스케줄러 설정

### 🪟 Windows (작업 스케줄러)

1. 시작 메뉴에서 **작업 스케줄러** 검색 후 실행
2. 우측 **기본 작업 만들기** 클릭
3. 이름 입력 (예: `Lotto Bot`)
4. 트리거: **매주** → 원하는 요일/시간 선택 (예: 토요일 오전 9시)
5. 동작: **프로그램 시작** 선택
6. 아래와 같이 입력:

| 항목 | 값 |
|------|----|
| 프로그램/스크립트 | python 경로 (예: `C:\Users\이름\AppData\Local\Programs\Python\Python3xx\python.exe`) |
| 인수 추가 | `lotto_bot.py` |
| 시작 위치 | lotto_bot 폴더 경로 (예: `C:\Users\이름\Dropbox\henry_lab\lotto_bot`) |

7. **마침** 클릭

> python 경로 확인 방법: cmd에서 `where python` 입력

---

### 🍎 Mac / 🐧 Linux (crontab)

터미널에서 crontab 편집기 열기:
```bash
crontab -e
```

아래 내용 추가 (매주 토요일 오전 9시 실행 예시):
```
0 9 * * 6 /usr/bin/python3 /Users/이름/lotto_bot/lotto_bot.py
```

crontab 형식 설명:
```
분 시 일 월 요일 명령어
0  9  *  *  6    → 매주 토요일(6) 오전 9시 0분
```

> 요일: 0=일요일, 1=월요일, 2=화요일, 3=수요일, 4=목요일, 5=금요일, 6=토요일

python 경로 확인:
```bash
which python3
```

저장 후 적용 확인:
```bash
crontab -l
```
