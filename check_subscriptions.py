import asyncio
import json
import random
import time
import logging
from typing import Optional
from urllib.parse import urlparse

import config
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("check_subscriptions")

def _pick_proxy() -> Optional[dict]:
    if not config.PROXIES:
        return None
    p = random.choice(config.PROXIES)
    proxy = {
        "server": f"http://{p['host']}:{p['port']}",
    }
    if p.get("username") and p.get("password"):
        proxy["username"] = p["username"]
        proxy["password"] = p["password"]
    return proxy


def _pick_user_agent() -> str:
    return random.choice(config.USER_AGENTS) if config.USER_AGENTS else None

def clean_target_account(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http"):
        parsed = urlparse(raw)
        path = parsed.path  # например: /proove_gaming_ua/
        username = path.strip("/").split("/")[0] if path else ""
        return username
    return raw.lstrip("@")

async def _load_cookies(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not isinstance(cookies, list):
            raise ValueError("Cookies file must contain a JSON list")

        # Нормализация поля sameSite
        for cookie in cookies:
            s = cookie.get("sameSite", "").lower()
            if s == "no_restriction":
                cookie["sameSite"] = "None"
            elif s == "unspecified":
                cookie["sameSite"] = "Lax"
            elif s == "lax":
                cookie["sameSite"] = "Lax"
            elif s == "strict":
                cookie["sameSite"] = "Strict"
            else:
                cookie["sameSite"] = "Lax"

        return cookies
    except FileNotFoundError:
        raise FileNotFoundError(f"Cookies file not found: {path}")
    except Exception:
        raise

async def check_instagram_follow(target_account: str, user_username: str, max_duration_sec: int = 30) -> bool:
    target_account = target_account.strip().lstrip("@")
    user_username = user_username.strip().lstrip("@")

    proxy = _pick_proxy()
    ua = _pick_user_agent()

    try:
        cookies = await _load_cookies(config.INSTAGRAM_COOKIES)
    except Exception as e:
        log.error(f"Failed to load Instagram cookies: {e}")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_args = {}
        if ua:
            context_args["user_agent"] = ua
        if proxy:
            context_args["proxy"] = proxy

        context = await browser.new_context(**context_args)
        try:
            await context.add_cookies(cookies)
        except Exception as e:
            log.error(f"Failed to add cookies: {e}")
            await context.close()
            await browser.close()
            return False

        page = await context.new_page()
        try:
            await page.goto(f"https://www.instagram.com/{target_account}/", timeout=60000)
            await asyncio.sleep(3)

            try:
                await page.click("a[href$='/followers/']", timeout=8000)
            except PlaywrightTimeoutError:
                anchors = await page.query_selector_all("header a")
                if anchors and len(anchors) >= 2:
                    await anchors[1].click()
                    await asyncio.sleep(2)
                else:
                    log.warning("Не удалось найти ссылку на подписчиков")
                    await context.close()
                    await browser.close()
                    return False

            await page.wait_for_selector("div[role='dialog']", timeout=10000)
            await asyncio.sleep(3)

            search_selectors = [
                "input[placeholder='Search']",
                "input[placeholder='Search users']",
                "input[placeholder='Search…']",
                "input[placeholder*='Search']",
                "input[type='text']"
            ]
            search_input = None
            for sel in search_selectors:
                try:
                    search_input = await page.wait_for_selector(sel, timeout=5000)
                    if search_input:
                        await search_input.fill(user_username)
                        break
                except PlaywrightTimeoutError:
                    continue

            if not search_input:
                log.warning("Поле поиска подписчиков не найдено")
                await context.close()
                await browser.close()
                return False

            await asyncio.sleep(3)  # Ждем подгрузки результатов поиска

            dialog = await page.query_selector("div[role='dialog']")
            if not dialog:
                log.warning("Диалог подписчиков не найден")
                await context.close()
                await browser.close()
                return False

            found = False
            start_time = time.time()
            while time.time() - start_time < max_duration_sec:
                user_divs = await dialog.query_selector_all("div > div > div > div")
                for div in user_divs:
                    try:
                        span = await div.query_selector("span")
                        if span:
                            span_text = (await span.inner_text()).strip().lower()
                            if user_username.lower() == span_text or user_username.lower() in span_text:
                                found = True
                                break
                    except Exception:
                        continue
                if found:
                    break

                await dialog.evaluate("(el) => { el.scrollBy(0, 400); }")
                await asyncio.sleep(2)

            await context.close()
            await browser.close()

            if found:
                return True
            else:
                log.info(f"Пользователь @{user_username} не найден в подписчиках {target_account}")
                return False

        except PlaywrightTimeoutError as e:
            log.error(f"Timeout при проверке Instagram: {e}")
            await context.close()
            await browser.close()
            return False
        except Exception as e:
            log.error(f"Ошибка в check_instagram_follow: {e}")
            await context.close()
            await browser.close()
            return False
        

async def check_tiktok_follow(target_account: str, user_username: str) -> bool:
    target_account = clean_target_account(target_account)
    user_username = user_username.strip().lstrip("@")

    proxy = _pick_proxy()
    ua = _pick_user_agent()
    cookies = await _load_cookies(config.TIKTOK_COOKIES)

    log.info(f"TT check: target={target_account} user={user_username} proxy={proxy}")

    # stealth JS injected into every page/context
    stealth_js = r"""
    (() => {
      try {
        // navigator.webdriver -> undefined
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // languages
        Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US'] });

        // plugins (fake)
        Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });

        // chrome object
        if (!window.chrome) {
          window.chrome = { runtime: {} };
        }

        // permissions query patch (so permissions.query won't reveal headless)
        try {
          const originalQuery = navigator.permissions.query;
          navigator.permissions.__query = originalQuery;
          navigator.permissions.query = (params) => {
            if (params && params.name === 'notifications') {
              return Promise.resolve({ state: Notification.permission });
            }
            return originalQuery(params);
          };
        } catch (e) {}

        // make webdriver configurable not present
        try {
          if (navigator.__proto__ && navigator.__proto__.hasOwnProperty('webdriver')) {
            delete navigator.__proto__.webdriver;
          }
        } catch (e) {}

        // hardwareConcurrency (best-effort, may be ignored)
        try {
          Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });
        } catch (e) {}

      } catch (err) {
        // ignore
      }
    })();
    """

    async with async_playwright() as p:
        # launch with some anti-detection args (keeps headless setting from config)
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--window-size=1920,1080",
        ]
        # keep user's HEADLESS flag, but if it's True we still pass it as is
        browser = await p.chromium.launch(headless=config.PLAYWRIGHT_HEADLESS, args=launch_args)

        context_args = {}
        # set viewport and UA for more realistic fingerprint
        context_args["viewport"] = {"width": 1920, "height": 1080}
        if ua:
            context_args["user_agent"] = ua
        else:
            # a reasonable default UA
            context_args["user_agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"

        # Add proxy to context if provided (optional)
        if proxy:
            context_args["proxy"] = proxy

        context = await browser.new_context(**context_args)

        # inject stealth script into every page
        try:
            await context.add_init_script(stealth_js)
        except Exception:
            # if add_init_script fails for any reason, continue — stealth still helps via UA/args
            log.warning("Не удалось добавить init script для stealth (игнорируем)")

        try:
            # add cookies (if provided)
            await context.add_cookies(cookies)
        except Exception as e:
            await browser.close()
            raise RuntimeError(f"Failed to add TT cookies: {e}")

        page = await context.new_page()

        profile_url = f"https://www.tiktok.com/@{target_account}"
        captcha_button_selector = "button.TUXButton.TUXButton--borderless.TUXButton--xsmall.TUXButton--secondary"

        # helper: try to detect & click captcha-close button (no exceptions thrown if absent)
        async def try_close_captcha():
            try:
                btn = await page.query_selector(captcha_button_selector)
                if btn:
                    try:
                        await btn.click()
                        log.info("Закрыли капчу (нажали на кнопку).")
                        # небольшая пауза после закрытия
                        await asyncio.sleep(random.uniform(2.0, 3.5))
                        return True
                    except Exception:
                        return False
            except Exception:
                return False
            return False

        # helper: small human-like movement
        async def humanize():
            try:
                await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                await asyncio.sleep(random.uniform(0.5, 1.2))
            except Exception:
                pass

        max_attempts = 3
        try:
            for attempt in range(1, max_attempts + 1):
                log.info(f"Attempt {attempt}: заходим на профиль {profile_url}")
                try:
                    await page.goto(profile_url, timeout=config.PLAYWRIGHT_TIMEOUT)
                except Exception as e:
                    log.warning(f"goto failed (attempt {attempt}): {e}")
                # подождать чуть дольше — чтобы страница прогрузилась и снизить риск капчи
                await asyncio.sleep(random.uniform(4.0, 6.5))

                # human moves
                await humanize()

                # try closing captcha if it appeared on profile
                await try_close_captcha()

                # click followers (Подписчики). Try both localized text variants
                clicked = False
                for sel in ("span:has-text('Подписчики')", "span:has-text('Followers')", "a[href$='/following/']"):
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            await el.click()
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    # fallback: try get_by_text (handles different node types)
                    try:
                        btn = page.get_by_text("Подписчики")
                        if await btn.count() > 0:
                            await btn.first.click()
                            clicked = True
                    except Exception:
                        pass

                if not clicked:
                    log.warning("Не удалось нажать на 'Подписчики' (продолжим попытку).")
                else:
                    log.info("Кликнули на 'Подписчики'")
                # дождёмся небольшой загрузки окна
                await asyncio.sleep(random.uniform(3.0, 5.0))

                # if captcha appeared after click, try to close and re-open followers once
                if await try_close_captcha():
                    # re-open followers to ensure modal is visible
                    try:
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        reopen = await page.query_selector("span:has-text('Подписчики')")
                        if reopen:
                            await reopen.click()
                            await asyncio.sleep(random.uniform(2.0, 3.0))
                    except Exception:
                        pass

                # wait for at least some list item to appear (li or p)
                try:
                    await page.wait_for_selector("li", timeout=15000)
                except Exception:
                    log.debug("li не появился вовремя, попробуем всё-таки искать по p внутри страницы.")

                # Now search through list items; do multiple smooth scrolls
                found = False
                scrolls = 25  # увеличено число скроллов для глубокого поиска
                for i in range(scrolls):
                    # get all <li> currently in DOM
                    try:
                        lis = await page.query_selector_all("li")
                    except Exception:
                        lis = []

                    # iterate and try to find <p> inside each li
                    for li in lis:
                        try:
                            p_el = await li.query_selector("p")
                            if not p_el:
                                continue
                            username_text = (await p_el.inner_text() or "").strip()
                            # normalize and compare
                            clean = username_text.lstrip("@").split()[0]  # take first token to be safe
                            if user_username.lower() == clean.lower() or user_username.lower() in username_text.lower():
                                log.info(f"Найден подписчик {user_username}")
                                found = True
                                break
                        except Exception:
                            continue
                    if found:
                        break

                    # human-like scroll inside the modal / page
                    # prefer scrolling modal if present
                    try:
                        # try to find scrollable container (modal or main feed)
                        modal = await page.query_selector("div[role='dialog']")
                        if modal:
                            # small scroll inside modal
                            await modal.evaluate("(el) => { el.scrollBy(0, 400); }")
                        else:
                            await page.mouse.wheel(0, 800)
                    except Exception:
                        try:
                            await page.mouse.wheel(0, 800)
                        except Exception:
                            pass

                    # random pause between scrolls
                    await asyncio.sleep(random.uniform(1.8, 3.2))

                    # occasionally perform small mouse move to look more human
                    if i % 4 == 0:
                        await humanize()

                    # also try to close captcha mid-scroll if it appears
                    await try_close_captcha()

                if found:
                    await context.close()
                    await browser.close()
                    return True

                log.info(f"Подписчик {user_username} не найден в этой попытке (attempt {attempt}).")
                # if not found, retry full flow (maybe proxy/session/timeout issue)
                await asyncio.sleep(random.uniform(2.5, 4.0))

            # after attempts
            await context.close()
            await browser.close()
            return False

        except Exception as e:
            log.exception(f"Error in check_tiktok_follow: {e}")
            try:
                await context.close()
                await browser.close()
            except Exception:
                pass
            return False
