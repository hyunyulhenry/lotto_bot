import time
import re
import os
import requests
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

load_dotenv()

# ==================== 설정 ====================
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')
BOT_HEADERS = {
    'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
    'Content-Type': 'application/json',
}

USER_ID = os.getenv('USER_ID')
PASSWORD = os.getenv('PASSWORD')
MIN_BALANCE = 10000

LOTTO_LOGIN_URL = 'https://www.dhlottery.co.kr/login'
LOTTO_HISTORY_URL = 'https://www.dhlottery.co.kr/mypage/mylotteryledger'
LOTTO_MYPAGE_URL = 'https://www.dhlottery.co.kr/mypage/home'
LOTTO_BUY_URL = 'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40'

# ==================== 디스코드 ====================
def discord_send(text):
    """웹훅으로 메시지 전송, message_id 반환"""
    res = requests.post(f'{DISCORD_WEBHOOK_URL}?wait=true', json={'content': text})
    return res.json() if res.status_code == 200 else {}

def discord_update(message_id, text):
    """웹훅으로 메시지 수정"""
    requests.patch(f'{DISCORD_WEBHOOK_URL}/messages/{message_id}', json={'content': text})

def discord_create_thread(message_id, name):
    """메시지에 스레드 생성, thread_id 반환"""
    url = f'https://discord.com/api/v10/channels/{DISCORD_CHANNEL_ID}/messages/{message_id}/threads'
    res = requests.post(url, headers=BOT_HEADERS, json={'name': name})
    return res.json().get('id') if res.status_code in (200, 201) else None

def discord_thread_send(thread_id, text):
    """봇 토큰으로 스레드에 메시지 전송"""
    url = f'https://discord.com/api/v10/channels/{thread_id}/messages'
    requests.post(url, headers=BOT_HEADERS, json={'content': text})

# ==================== 유틸 ====================
def extract_balance(text):
    return int(''.join(re.findall(r'\d+', text)))

def format_lotto_history(df):
    emoji = {'낙첨': '❌', '미추첨': '⏳'}
    lines = ['📃 로또 구매 내역:\n']
    for _, row in df.iterrows():
        e = emoji.get(row['당첨결과'], '✅')
        lines.append(f"{row['구입일자']} | {row['회차']}회 | {e} {row['당첨결과']} | {row['당첨금']}")
    return '\n'.join(lines)

def create_driver():
    options = webdriver.ChromeOptions()
    for arg in ['--start-maximized', '--disable-blink-features=AutomationControlled',
                '--headless', '--no-sandbox', '--disable-dev-shm-usage']:
        options.add_argument(arg)
    return webdriver.Chrome(service=Service(), options=options)

def wait_and_click(driver, xpath, timeout=10):
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xpath))).click()

def wait_for(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

# ==================== 단계별 실행 ====================
def login(driver):
    driver.get(LOTTO_LOGIN_URL)
    wait_for(driver, By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[1]/input')
    driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[1]/input').send_keys(USER_ID)
    time.sleep(1)
    driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[2]/input').send_keys(PASSWORD)
    time.sleep(1)
    driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/button').click()
    time.sleep(3)

def get_purchase_history(driver):
    driver.get(LOTTO_HISTORY_URL)
    time.sleep(2)

    try:
        wait_and_click(driver, '/html/body/div[4]/div[2]/div/div/div/form/div[1]/div/div[2]/div/div/div[2]/div[2]/button[3]')
        time.sleep(1)
    except Exception:
        pass

    try:
        wait_and_click(driver, '/html/body/div[4]/div[2]/div/div/div/form/div[2]/button')
        time.sleep(2)
    except Exception:
        pass

    rows = driver.find_element(By.CLASS_NAME, 'whl-body').find_elements(By.CLASS_NAME, 'whl-row')
    if not rows:
        return '조회 결과가 없습니다.'

    data = []
    for row in rows:
        row_data = [col.text.strip() for col in row.find_elements(By.CLASS_NAME, 'whl-txt')]
        if row_data:
            data.append(row_data)

    columns = ['구입일자', '복권명', '회차', '선택번호/복권번호', '구입매수', '당첨결과', '당첨금', '추첨일자/당첨일자', '고액당첨인증/수령여부']
    df = pd.DataFrame(data, columns=columns)
    return format_lotto_history(df[['구입일자', '회차', '당첨결과', '당첨금']])

def get_balance(driver):
    driver.get(LOTTO_MYPAGE_URL)
    time.sleep(2)
    return driver.find_element(By.XPATH, '/html/body/div[4]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[2]/span[1]').text

def buy_lotto(driver):
    driver.get(LOTTO_BUY_URL)
    time.sleep(2)

    wait_for(driver, By.CSS_SELECTOR, '#ifrm_tab')
    driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, '#ifrm_tab'))

    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//*[@id="checkNumGroup"]/div[1]/label/span'))
    )
    driver.find_element(By.XPATH, '//*[@id="checkNumGroup"]/div[1]/label/span').click()
    time.sleep(1)
    driver.find_element(By.XPATH, '//*[@id="amoundApply"]/option[5]').click()
    time.sleep(1)
    driver.find_element(By.XPATH, '//*[@id="btnSelectNum"]').click()
    time.sleep(1)
    driver.find_element(By.XPATH, '//*[@id="btnBuy"]').click()
    time.sleep(1)
    driver.find_element(By.XPATH, '//*[@id="popupLayerConfirm"]/div/div[2]/input[1]').click()
    time.sleep(1)
    driver.find_element(By.XPATH, '//*[@id="closeLayer"]').click()

    driver.switch_to.default_content()

# ==================== 메인 ====================
def main():
    today = datetime.today().strftime('%Y-%m-%d')

    # 디스코드 시작 메시지
    result = discord_send(f"⏳ {today} 로또 구매를 시작합니다.")
    message_id = result.get('id')
    thread_id = [None]

    def reply(text):
        if not thread_id[0]:
            thread_id[0] = discord_create_thread(message_id, f'{today} 로또 구매')
        discord_thread_send(thread_id[0], text)

    success = False
    fail_reason = '알 수 없는 오류'
    driver = create_driver()

    try:
        # 1. 로그인
        try:
            login(driver)
        except Exception as e:
            reply(f"❌ 로그인 실패: {e}")
            fail_reason = '로그인 실패'
            return

        # 2. 구매내역 조회
        try:
            reply(get_purchase_history(driver))
        except Exception as e:
            reply(f'❌ 구매내역 조회 실패: {e}')

        # 3. 잔액 확인
        try:
            money = get_balance(driver)
            reply(f"💵 현재 잔액은 {money} 입니다.")
            balance = extract_balance(money)

            if balance == 0:
                reply("❌ 잔액이 0원입니다. 충전하세요!")
                fail_reason = '잔액 부족 (0원)'
                return
            elif balance <= MIN_BALANCE:
                reply("⚠️ 잔액이 부족합니다. 충전하세요!")
        except Exception as e:
            reply(f"❌ 잔액 확인 실패: {e}")
            fail_reason = '잔액 확인 실패'
            return

        # 4. 로또 구매
        try:
            buy_lotto(driver)
            reply('💸 구매를 완료했습니다.')
            success = True
        except Exception as e:
            error_msg = str(e)
            if 'not interactable' in error_msg or 'not clickable' in error_msg:
                reply('⚠️ 이번 주 구매한도를 모두 채웠습니다.')
                fail_reason = '구매한도 초과'
            else:
                reply(f'❌ 구매 실패: {error_msg}')
                fail_reason = f'구매 오류 ({error_msg[:30]})'
            return

        # 5. 최종 잔액 확인
        try:
            money_now = get_balance(driver)
            reply(f"💵 남은 잔액은 {money_now} 입니다.")
        except Exception as e:
            reply(f"❌ 최종 잔액 확인 실패: {e}")

    except Exception as e:
        reply(f"❌ 예상치 못한 오류: {e}")
        fail_reason = '예상치 못한 오류'

    finally:
        if success:
            discord_update(message_id, f"✅ {today} 로또 구매를 완료했습니다.")
        else:
            discord_update(message_id, f"❌ {today} 로또 구매를 실패했습니다. ({fail_reason})")
        driver.quit()

if __name__ == "__main__":
    main()
