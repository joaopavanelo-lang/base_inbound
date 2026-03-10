import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import os
import shutil
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials

DOWNLOAD_DIR = "/tmp"
DEBUG_DIR = "/tmp/debug"

def rename_downloaded_file(download_dir, download_path):
    try:
        current_hour = datetime.now().strftime("%H")
        new_file_name = f"PROD-{current_hour}.csv"
        new_file_path = os.path.join(download_dir, new_file_name)
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
        shutil.move(download_path, new_file_path)
        print(f"Arquivo salvo como: {new_file_path}")
        return new_file_path
    except Exception as e:
        print(f"Erro ao renomear o arquivo: {e}")
        return None

def update_packing_google_sheets(csv_file_path):
    try:
        if not os.path.exists(csv_file_path):
            print(f"Arquivo {csv_file_path} não encontrado.")
            return
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name("hxh.json", scope)
        client = gspread.authorize(creds)
        sheet1 = client.open_by_url(
            "https://docs.google.com/spreadsheets/d/1LZ8WUrgN36Hk39f7qDrsRwvvIy1tRXLVbl3-wSQn-Pc/edit?gid=734921183#gid=734921183"
        )
        worksheet1 = sheet1.worksheet("Base Inbound")
        df = pd.read_csv(csv_file_path).fillna("")
        worksheet1.clear()
        worksheet1.update([df.columns.values.tolist()] + df.values.tolist())
        print(f"Arquivo enviado com sucesso para a aba 'Base Inbound'.")
    except Exception as e:
        print(f"Erro durante o processo: {e}")

async def screenshot(page, name):
    """Salva screenshot com nome para debug"""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=True)
    print(f"📸 Screenshot: {path}")

async def dump_page_tabs(page):
    """Lista todos os textos de spans/tabs visíveis para debug"""
    tabs = await page.evaluate("""
        () => {
            const elements = document.querySelectorAll('span, div[role="tab"], a[role="tab"], .ant-tabs-tab, [class*="tab"]');
            const results = [];
            for (const el of elements) {
                const text = el.textContent.trim();
                const rect = el.getBoundingClientRect();
                if (text && rect.width > 0 && rect.height > 0 && text.length < 50) {
                    results.push({
                        tag: el.tagName,
                        text: text,
                        class: el.className.substring(0, 80),
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        w: Math.round(rect.width),
                        h: Math.round(rect.height)
                    });
                }
            }
            return results;
        }
    """)
    print("\n🔍 Elementos visíveis (tabs/spans):")
    for t in tabs:
        if any(keyword in t['text'].lower() for keyword in ['inbound', 'outbound', 'trip', 'export', 'viagem']):
            print(f"  ✅ <{t['tag']}> '{t['text']}' class='{t['class']}' pos=({t['x']},{t['y']}) size=({t['w']}x{t['h']})")
    return tabs

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
            ],
        )

        context = await browser.new_context(
            accept_downloads=True,
            permissions=["geolocation"],
            geolocation={"latitude": -23.55052, "longitude": -46.633308},
            viewport={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        try:
            # ========================
            # LOGIN
            # ========================
            await page.goto("https://spx.shopee.com.br/")
            await page.wait_for_selector(
                'xpath=//*[@placeholder="Ops ID"]', timeout=15000
            )
            await page.locator('xpath=//*[@placeholder="Ops ID"]').fill("Ops292298")
            await page.locator('xpath=//*[@placeholder="Senha"]').fill("@Shopee123")
            await page.locator(
                'xpath=/html/body/div[1]/div/div[2]/div/div/div[1]/div[3]/form/div/div/button'
            ).click()
            await page.wait_for_timeout(15000)

            # Fechar pop-ups
            try:
                await page.locator(".ssc-dialog-close").click(timeout=5000)
                print("Pop-up fechado.")
            except:
                print("Nenhum pop-up foi encontrado.")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(2000)

            await screenshot(page, "01_apos_login")

            # ========================
            # NAVEGAR PARA A PÁGINA
            # ========================
            await page.goto("https://spx.shopee.com.br/#/hubLinehaulTrips/trip")
            await page.wait_for_timeout(10000)

            # Fechar modais
            for i in range(3):
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(1000)

            await screenshot(page, "02_pagina_trip")

            # ========================
            # DEBUG: listar elementos
            # ========================
            tabs = await dump_page_tabs(page)

            # ========================
            # CLICAR EM "Inbound"
            # ========================
            inbound_clicked = False

            # --- Estratégia 1: dispatchEvent completo (funciona com Vue/React) ---
            try:
                result = await page.evaluate("""
                    () => {
                        const spans = document.querySelectorAll('span');
                        for (const span of spans) {
                            if (span.textContent.trim() === 'Inbound') {
                                // Simula eventos completos do mouse
                                const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                                for (const eventType of events) {
                                    const event = new MouseEvent(eventType, {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    span.dispatchEvent(event);
                                }
                                return 'clicked: ' + span.textContent.trim();
                            }
                        }
                        // Tenta também em divs e outros elementos
                        const allEls = document.querySelectorAll('div, a, li, button');
                        for (const el of allEls) {
                            if (el.textContent.trim() === 'Inbound' || 
                                el.innerText.trim() === 'Inbound') {
                                const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                                for (const eventType of events) {
                                    const event = new MouseEvent(eventType, {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    el.dispatchEvent(event);
                                }
                                return 'clicked (non-span): ' + el.tagName;
                            }
                        }
                        return 'not_found';
                    }
                """)
                print(f"Estratégia 1 (dispatchEvent): {result}")
                if 'clicked' in result:
                    inbound_clicked = True
            except Exception as e:
                print(f"Estratégia 1 falhou: {e}")

            await page.wait_for_timeout(3000)
            await screenshot(page, "03_apos_click_estrategia1")

            # --- Estratégia 2: Clicar por coordenadas do elemento ---
            if not inbound_clicked:
                try:
                    coords = await page.evaluate("""
                        () => {
                            const spans = document.querySelectorAll('span');
                            for (const span of spans) {
                                if (span.textContent.trim() === 'Inbound') {
                                    const rect = span.getBoundingClientRect();
                                    return {x: rect.x + rect.width/2, y: rect.y + rect.height/2};
                                }
                            }
                            return null;
                        }
                    """)
                    if coords:
                        print(f"Estratégia 2: clicando em coordenadas ({coords['x']}, {coords['y']})")
                        await page.mouse.click(coords['x'], coords['y'])
                        inbound_clicked = True
                        await page.wait_for_timeout(3000)
                        await screenshot(page, "04_apos_click_coordenadas")
                except Exception as e:
                    print(f"Estratégia 2 falhou: {e}")

            # --- Estratégia 3: Clicar no PARENT do span ---
            if not inbound_clicked:
                try:
                    result = await page.evaluate("""
                        () => {
                            const spans = document.querySelectorAll('span');
                            for (const span of spans) {
                                if (span.textContent.trim() === 'Inbound') {
                                    let parent = span.parentElement;
                                    for (let i = 0; i < 3 && parent; i++) {
                                        const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                                        for (const eventType of events) {
                                            parent.dispatchEvent(new MouseEvent(eventType, {
                                                bubbles: true, cancelable: true, view: window
                                            }));
                                        }
                                        parent = parent.parentElement;
                                    }
                                    return 'clicked parents';
                                }
                            }
                            return 'not_found';
                        }
                    """)
                    print(f"Estratégia 3 (parent click): {result}")
                    if 'clicked' in result:
                        inbound_clicked = True
                except Exception as e:
                    print(f"Estratégia 3 falhou: {e}")

            await page.wait_for_timeout(5000)
            await screenshot(page, "05_antes_exportar")

            # ========================
            # DEBUG: ver o estado da página após o clique
            # ========================
            current_url = page.url
            print(f"\n📍 URL atual: {current_url}")
            
            # Verificar se o botão Exportar existe
            exportar_count = await page.get_by_role("button", name="Exportar").count()
            print(f"🔎 Botões 'Exportar' encontrados: {exportar_count}")
            
            # Listar TODOS os botões visíveis
            buttons = await page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, [role="button"]');
                    const results = [];
                    for (const btn of btns) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            results.push({
                                text: btn.textContent.trim().substring(0, 40),
                                tag: btn.tagName,
                                class: btn.className.substring(0, 60)
                            });
                        }
                    }
                    return results;
                }
            """)
            print("\n🔘 Botões visíveis:")
            for b in buttons:
                print(f"  - '{b['text']}' ({b['tag']}, class={b['class']})")

            # ========================
            # EXPORTAR
            # ========================
            if exportar_count > 0:
                await page.get_by_role("button", name="Exportar").nth(0).click()
                await page.wait_for_timeout(10000)

                # DOWNLOAD
                await page.goto(
                    "https://spx.shopee.com.br/#/taskCenter/exportTaskCenter"
                )
                await page.wait_for_timeout(8000)
                async with page.expect_download() as download_info:
                    await page.get_by_role("button", name="Baixar").nth(0).click()
                download = await download_info.value
                download_path = os.path.join(DOWNLOAD_DIR, download.suggested_filename)
                await download.save_as(download_path)
                new_file_path = rename_downloaded_file(DOWNLOAD_DIR, download_path)

                if new_file_path:
                    update_packing_google_sheets(new_file_path)
                print("✅ Dados atualizados com sucesso.")
            else:
                print("❌ Botão Exportar não encontrado. Veja os screenshots em /tmp/debug/")

        except Exception as e:
            await screenshot(page, "99_erro_final")
            print(f"Erro durante o processo: {e}")
        finally:
            await browser.close()

if _name_ == "_main_":
    asyncio.run(main())
