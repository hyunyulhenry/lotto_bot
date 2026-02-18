import time
import re
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import pandas as pd
import os

# ==================== 환경변수 로드 ====================
load_dotenv()

SLACK_TOKEN = os.getenv('SLACK_TOKEN')
SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
SLACK_POST_URL = 'https://slack.com/api/chat.postMessage'
SLACK_UPDATE_URL = 'https://slack.com/api/chat.update'

USER_ID = os.getenv('USER_ID')
PASSWORD = os.getenv('PASSWORD')
MIN_BALANCE = 10000

# ==================== 함수 정의 ====================
def send_slack(text, thread_ts=None):
    """슬랙 메시지 전송"""
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {'channel': SLACK_CHANNEL, 'text': text}
    if thread_ts:
        payload['thread_ts'] = thread_ts

    response = requests.post(SLACK_POST_URL, headers=headers, json=payload)
    result = response.json()

    if not result.get('ok'):
        print(f"[Slack 전송 실패] {result.get('error')}")

    return result

def update_slack(ts, text):
    """슬랙 메시지 수정"""
    headers = {
        'Authorization': f'Bearer {SLACK_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {'channel': SLACK_CHANNEL, 'ts': ts, 'text': text}

    response = requests.post(SLACK_UPDATE_URL, headers=headers, json=payload)
    result = response.json()

    if not result.get('ok'):
        print(f"[Slack 수정 실패] {result.get('error')}")

    return result

def format_lotto_history(df):
    """로또 구매 내역을 한 줄 형식으로 변환"""
    lines = ['📃 로또 구매 내역:\n']
    for _, row in df.iterrows():
        당첨결과 = row['당첨결과']
        당첨금 = row['당첨금']

        if 당첨결과 == '낙첨':
            결과이모지 = '❌'
        elif 당첨결과 == '미추첨':
            결과이모지 = '⏳'
        else:
            결과이모지 = '✅'

        lines.append(f"{row['구입일자']} | {row['회차']}회 | {결과이모지} {당첨결과} | {당첨금}")

    return '\n'.join(lines)

def wait_and_click(driver, xpath, timeout=10):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element

def get_text(driver, xpath):
    return driver.find_element(By.XPATH, xpath).text

def extract_balance(text):
    return int(''.join(re.findall(r'\d+', text)))

# ==================== 메인 실행 ====================
def main():
    today = datetime.today().strftime('%Y-%m-%d')

    # 시작 메시지
    start_result = send_slack(f"⏳ {today} 로또 구매를 시작합니다.")
    thread_ts = start_result.get('ts')
    success = False
    fail_reason = '알 수 없는 오류'

    # 드라이버 설정
    service = Service()
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(service=service, options=options)

    try:
        # ========== 1. 로그인 ==========
        print("=== 로그인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/login')
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[1]/input'))
            )
            driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[1]/input').send_keys(USER_ID)
            time.sleep(1)
            driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[2]/input').send_keys(PASSWORD)
            time.sleep(1)
            driver.find_element(By.XPATH, '/html/body/div[4]/div[1]/div/div/form/div/div[2]/button').click()
            time.sleep(3)
            print("✓ 로그인 완료")
        except Exception as e:
            send_slack(f"❌ 로그인 실패: {str(e)}", thread_ts=thread_ts)
            fail_reason = '로그인 실패'
            print(f"✗ 로그인 실패: {e}")
            return

        # ========== 2. 구매내역 조회 ==========
        print("\n=== 구매내역 조회 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/mylotteryledger')
            time.sleep(2)

            try:
                wait_and_click(driver, '/html/body/div[4]/div[2]/div/div/div/form/div[1]/div/div[2]/div/div/div[2]/div[2]/button[3]')
                time.sleep(1)
            except Exception as e:
                print(f"✗ 기간 선택 실패: {e}")

            try:
                wait_and_click(driver, '/html/body/div[4]/div[2]/div/div/div/form/div[2]/button')
                time.sleep(2)
            except Exception as e:
                print(f"✗ 검색 실패: {e}")

            whl_body = driver.find_element(By.CLASS_NAME, 'whl-body')
            rows = whl_body.find_elements(By.CLASS_NAME, 'whl-row')

            if rows:
                data = []
                for row in rows:
                    cols = row.find_elements(By.CLASS_NAME, 'whl-txt')
                    row_data = [col.text.strip() for col in cols]
                    if row_data:
                        data.append(row_data)

                columns = ['구입일자', '복권명', '회차', '선택번호/복권번호', '구입매수', '당첨결과', '당첨금', '추첨일자/당첨일자', '고액당첨인증/수령여부']
                df = pd.DataFrame(data, columns=columns)
                df_selected = df[['구입일자', '회차', '당첨결과', '당첨금']]

                tbl_results = format_lotto_history(df_selected)
                send_slack(tbl_results, thread_ts=thread_ts)
                print("✓ 구매내역 전송 완료")
            else:
                send_slack('조회 결과가 없습니다.', thread_ts=thread_ts)

        except Exception as e:
            send_slack(f'❌ 구매내역 조회 실패: {str(e)}', thread_ts=thread_ts)
            print(f"✗ 구매내역 조회 실패: {e}")

        # ========== 3. 잔액 확인 ==========
        print("\n=== 잔액 확인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/home')
            time.sleep(2)

            money = get_text(driver, '/html/body/div[4]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[2]/span[1]')
            send_slack(f"💵 현재 잔액은 {money} 입니다.", thread_ts=thread_ts)
            print(f"✓ 현재 잔액: {money}")

            balance = extract_balance(money)

            if balance == 0:
                send_slack("❌ 잔액이 0원입니다. 충전하세요!", thread_ts=thread_ts)
                fail_reason = '잔액 부족 (0원)'
                print("❌ 잔액 0원 - 구매 불가")
                return
            elif balance <= MIN_BALANCE:
                send_slack("⚠️ 잔액이 부족합니다. 충전하세요!", thread_ts=thread_ts)

        except Exception as e:
            send_slack(f"❌ 잔액 확인 실패: {str(e)}", thread_ts=thread_ts)
            fail_reason = '잔액 확인 실패'
            print(f"✗ 잔액 확인 실패: {e}")
            return

        # ========== 4. 로또 구매 ==========
        print("\n=== 로또 구매 ===")
        try:
            driver.get('https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40')
            time.sleep(2)

            driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, '#ifrm_tab'))
            time.sleep(1)

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

            send_slack('💸 구매를 완료했습니다.', thread_ts=thread_ts)
            success = True
            print("✓ 로또 구매 완료")

        except Exception as e:
            error_msg = str(e)
            if 'not interactable' in error_msg or 'not clickable' in error_msg:
                send_slack('⚠️ 이번 주 구매한도를 모두 채웠습니다.', thread_ts=thread_ts)
                fail_reason = '구매한도 초과'
                print("⚠️ 구매 한도 초과")
            else:
                send_slack(f'❌ 구매 실패: {error_msg}', thread_ts=thread_ts)
                fail_reason = f'구매 오류 ({error_msg[:30]})'
                print(f"✗ 구매 실패: {e}")
            return

        driver.switch_to.default_content()
        time.sleep(1)

        # ========== 5. 최종 잔액 확인 ==========
        print("\n=== 최종 잔액 확인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/home')
            time.sleep(2)

            money_now = get_text(driver, '/html/body/div[4]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[2]/span[1]')
            send_slack(f"💵 남은 잔액은 {money_now} 입니다.", thread_ts=thread_ts)
            print(f"✓ 남은 잔액: {money_now}")
        except Exception as e:
            send_slack(f"❌ 최종 잔액 확인 실패: {str(e)}", thread_ts=thread_ts)
            print(f"✗ 최종 잔액 확인 실패: {e}")

    except Exception as e:
        send_slack(f"❌ 예상치 못한 오류: {str(e)}", thread_ts=thread_ts)
        fail_reason = '예상치 못한 오류'
        print(f"✗ 예상치 못한 오류: {e}")

    finally:
        # ========== 시작 메시지 업데이트 ==========
        if success:
            update_slack(thread_ts, f"✅ {today} 로또 구매를 완료했습니다.")
        else:
            update_slack(thread_ts, f"❌ {today} 로또 구매를 실패했습니다. ({fail_reason})")

        driver.quit()
        print("\n=== 완료 ===")

# ==================== 실행 ====================
if __name__ == "__main__":
    main()
