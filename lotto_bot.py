import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from slack_sdk import WebClient
import os

# ==================== 환경변수 ====================
load_dotenv()

SLACK_CHANNEL = os.getenv('SLACK_CHANNEL')
USER_ID = os.getenv('USER_ID')
PASSWORD = os.getenv('PASSWORD')
MIN_BALANCE = 10000

_required = {'SLACK_TOKEN': os.getenv('SLACK_TOKEN'), 'SLACK_CHANNEL': SLACK_CHANNEL, 'USER_ID': USER_ID, 'PASSWORD': PASSWORD}
_missing = [k for k, v in _required.items() if not v]
if _missing:
    raise EnvironmentError(f"환경변수 누락: {', '.join(_missing)}")

client = WebClient(token=os.getenv('SLACK_TOKEN'))

# ==================== XPath 상수 ====================
LOGIN_ID    = '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[1]/input'
LOGIN_PW    = '/html/body/div[4]/div[1]/div/div/form/div/div[2]/div[2]/input'
LOGIN_BTN   = '/html/body/div[4]/div[1]/div/div/form/div/div[2]/button'
PERIOD_BTN  = '/html/body/div[4]/div[2]/div/div/div/form/div[1]/div/div[2]/div/div/div[2]/div[2]/button[3]'
SEARCH_BTN  = '/html/body/div[4]/div[2]/div/div/div/form/div[2]/button'
BALANCE_SPAN = '/html/body/div[4]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[2]/span[1]'

PURCHASE_STEPS = [
    '//*[@id="checkNumGroup"]/div[1]/label/span',
    '//*[@id="amoundApply"]/option[5]',
    '//*[@id="btnSelectNum"]',
    '//*[@id="btnBuy"]',
    '//*[@id="popupLayerConfirm"]/div/div[2]/input[1]',
    '//*[@id="closeLayer"]',
]

RESULT_EMOJI = {'낙첨': '❌', '미추첨': '⏳'}

# ==================== 함수 ====================
def send_slack(text, thread_ts=None):
    try:
        return client.chat_postMessage(channel=SLACK_CHANNEL, text=text, thread_ts=thread_ts)
    except Exception as e:
        print(f"[Slack 전송 실패] {e}")
        return {}

def update_slack(ts, text):
    try:
        return client.chat_update(channel=SLACK_CHANNEL, ts=ts, text=text)
    except Exception as e:
        print(f"[Slack 수정 실패] {e}")
        return {}

def format_lotto_history(data):
    lines = ['📃 로또 구매 내역:\n']
    for row in data:
        emoji = RESULT_EMOJI.get(row[5], '✅')
        lines.append(f"{row[0]} | {row[2]}회 | {emoji} {row[5]} | {row[6]}")
    return '\n'.join(lines)

def wait_and_click(driver, xpath, timeout=10):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element

def get_balance(driver):
    text = driver.find_element(By.XPATH, BALANCE_SPAN).text
    amount = int(''.join(re.findall(r'\d+', text)))
    return text, amount

def create_driver():
    options = webdriver.ChromeOptions()
    for arg in ['--disable-blink-features=AutomationControlled', '--headless', '--no-sandbox', '--disable-dev-shm-usage']:
        options.add_argument(arg)
    return webdriver.Chrome(service=Service(), options=options)

# ==================== 메인 ====================
def main():
    today = datetime.today().strftime('%Y-%m-%d')

    start_result = send_slack(f"⏳ {today} 로또 구매를 시작합니다.")
    thread_ts = start_result.get('ts')
    success = False
    fail_reason = '알 수 없는 오류'

    driver = create_driver()

    try:
        # 1. 로그인
        print("=== 로그인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/login')
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, LOGIN_ID)))
            driver.find_element(By.XPATH, LOGIN_ID).send_keys(USER_ID)
            time.sleep(1)
            driver.find_element(By.XPATH, LOGIN_PW).send_keys(PASSWORD)
            time.sleep(1)
            driver.find_element(By.XPATH, LOGIN_BTN).click()
            time.sleep(3)
            print("✓ 로그인 완료")
        except Exception as e:
            send_slack(f"❌ 로그인 실패: {e}", thread_ts=thread_ts)
            fail_reason = '로그인 실패'
            print(f"✗ 로그인 실패: {e}")
            return

        # 2. 구매내역 조회
        print("\n=== 구매내역 조회 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/mylotteryledger')
            time.sleep(2)

            try:
                wait_and_click(driver, PERIOD_BTN)
                time.sleep(1)
            except Exception as e:
                print(f"✗ 기간 선택 실패: {e}")

            try:
                wait_and_click(driver, SEARCH_BTN)
                time.sleep(2)
            except Exception as e:
                print(f"✗ 검색 실패: {e}")

            rows = driver.find_element(By.CLASS_NAME, 'whl-body').find_elements(By.CLASS_NAME, 'whl-row')
            if rows:
                data = []
                for row in rows:
                    cols = [col.text.strip() for col in row.find_elements(By.CLASS_NAME, 'whl-txt')]
                    if cols:
                        data.append(cols)
                send_slack(format_lotto_history(data), thread_ts=thread_ts)
                print("✓ 구매내역 전송 완료")
            else:
                send_slack('조회 결과가 없습니다.', thread_ts=thread_ts)

        except Exception as e:
            send_slack(f'❌ 구매내역 조회 실패: {e}', thread_ts=thread_ts)
            print(f"✗ 구매내역 조회 실패: {e}")

        # 3. 잔액 확인
        print("\n=== 잔액 확인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/home')
            time.sleep(2)

            money, balance = get_balance(driver)
            send_slack(f"💵 현재 잔액은 {money} 입니다.", thread_ts=thread_ts)
            print(f"✓ 현재 잔액: {money}")

            if balance == 0:
                send_slack("❌ 잔액이 0원입니다. 충전하세요!", thread_ts=thread_ts)
                fail_reason = '잔액 부족 (0원)'
                print("❌ 잔액 0원 - 구매 불가")
                return
            elif balance <= MIN_BALANCE:
                send_slack("⚠️ 잔액이 부족합니다. 충전하세요!", thread_ts=thread_ts)

        except Exception as e:
            send_slack(f"❌ 잔액 확인 실패: {e}", thread_ts=thread_ts)
            fail_reason = '잔액 확인 실패'
            print(f"✗ 잔액 확인 실패: {e}")
            return

        # 4. 로또 구매
        print("\n=== 로또 구매 ===")
        try:
            driver.get('https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40')
            time.sleep(2)

            driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, '#ifrm_tab'))
            time.sleep(1)

            for xpath in PURCHASE_STEPS:
                driver.find_element(By.XPATH, xpath).click()
                time.sleep(1)

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

        # 5. 최종 잔액 확인
        print("\n=== 최종 잔액 확인 ===")
        try:
            driver.get('https://www.dhlottery.co.kr/mypage/home')
            time.sleep(2)

            money_now, _ = get_balance(driver)
            send_slack(f"💵 남은 잔액은 {money_now} 입니다.", thread_ts=thread_ts)
            print(f"✓ 남은 잔액: {money_now}")
        except Exception as e:
            send_slack(f"❌ 최종 잔액 확인 실패: {e}", thread_ts=thread_ts)
            print(f"✗ 최종 잔액 확인 실패: {e}")

    except Exception as e:
        send_slack(f"❌ 예상치 못한 오류: {e}", thread_ts=thread_ts)
        fail_reason = '예상치 못한 오류'
        print(f"✗ 예상치 못한 오류: {e}")

    finally:
        if success:
            update_slack(thread_ts, f"✅ {today} 로또 구매를 완료했습니다.")
        else:
            update_slack(thread_ts, f"❌ {today} 로또 구매를 실패했습니다. ({fail_reason})")

        driver.quit()
        print("\n=== 완료 ===")

if __name__ == "__main__":
    main()
