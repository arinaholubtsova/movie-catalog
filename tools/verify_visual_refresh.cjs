const { chromium } = require('playwright');
const { randomBytes } = require('crypto');
const fs = require('fs');
const path = require('path');

async function main() {
  const port = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../.run/processes.json'), 'utf8')).frontend_port;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const email = `visual-${Date.now()}@example.com`;
  const password = randomBytes(18).toString('base64url');
  try {
    await page.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });
    await page.getByRole('button', { name: 'Відкрити Interstellar' }).waitFor();
    if (await page.locator('.poster-grid img').count() < 12) throw new Error('Catalog posters are missing');
    const broken = await page.locator('.poster-grid img').evaluateAll(images => images.filter(image => !image.complete || image.naturalWidth === 0).map(image => image.src));
    if (broken.length) throw new Error(`Broken posters: ${broken.join(', ')}`);
    await page.screenshot({ path: path.resolve(__dirname, '../.run/catalog-redesign.png'), fullPage: true });

    await page.getByRole('tab', { name: 'Зареєструватися' }).click();
    if (await page.getByRole('tab', { name: 'Зареєструватися' }).getAttribute('aria-selected') !== 'true') throw new Error('Registration tab is not selected');
    await page.screenshot({ path: path.resolve(__dirname, '../.run/auth-redesign.png') });
    await page.getByRole('textbox', { name: 'Email' }).fill(email);
    await page.getByRole('textbox', { name: 'Пароль' }).fill(password);
    await page.getByRole('button', { name: 'Створити обліковий запис' }).click();
    await page.getByRole('tab', { name: 'Увійти' }).waitFor();
    await page.getByRole('button', { name: 'Увійти →' }).click();
    await page.getByRole('button', { name: 'Профіль' }).waitFor();

    await page.getByRole('button', { name: 'Відкрити Interstellar' }).click();
    await page.getByRole('heading', { name: 'Interstellar' }).waitFor();
    await page.getByText('Оцініть за шкалою 1–5.').waitFor();
    await page.getByRole('button', { name: 'Оцінити на 4 з 5' }).click();
    await page.getByText('4 / 5').waitFor();
    await page.getByRole('button', { name: /Улюблене/ }).click();
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent?.includes('Улюблене') && button.getAttribute('aria-pressed') === 'true'));
    await page.screenshot({ path: path.resolve(__dirname, '../.run/detail-redesign.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    const mobileLabels = await page.locator('.mobile-nav button').allTextContents();
    for (const label of ['Каталог', 'Для вас', 'Улюблені', 'Хочу подивитися', 'Ще']) {
      if (!mobileLabels.some(text => text.includes(label))) throw new Error(`Mobile navigation is missing: ${label}`);
    }
    await page.locator('.mobile-nav button').filter({ hasText: 'Ще' }).click();
    const moreLabels = await page.locator('.mobile-more-menu button').allTextContents();
    for (const label of ['Переглянуті', 'Історія', 'Профіль']) {
      if (!moreLabels.some(text => text.includes(label))) throw new Error(`Mobile more menu is missing: ${label}`);
    }
    await page.screenshot({ path: path.resolve(__dirname, '../.run/detail-mobile-redesign.png'), fullPage: true });
    const detailOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (detailOverflow > 0) throw new Error(`Mobile detail horizontal overflow: ${detailOverflow}px`);
    await page.locator('.mobile-more-menu button').filter({ hasText: 'Історія' }).click();
    await page.getByRole('heading', { name: 'Історія' }).waitFor();
    await page.locator('.history-movie').filter({ hasText: 'Interstellar' }).first().waitFor();
    await page.locator('.history-movie').filter({ hasText: 'Interstellar' }).first().click();
    await page.getByRole('heading', { name: 'Interstellar' }).waitFor();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.getByRole('button', { name: /Улюблене/ }).click();
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(button => button.textContent?.includes('Улюблене') && button.getAttribute('aria-pressed') === 'false'));
    await page.getByRole('button', { name: 'Профіль' }).click();
    await page.getByRole('textbox', { name: 'Пароль для видалення' }).fill(password);
    await page.getByRole('textbox', { name: 'Підтвердження DELETE' }).fill('DELETE');
    await page.getByRole('button', { name: 'Видалити профіль' }).click();
    await page.getByText('Обліковий запис видалено').waitFor();

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    await mobile.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });
    await mobile.getByRole('button', { name: 'Відкрити Interstellar' }).waitFor();
    await mobile.screenshot({ path: path.resolve(__dirname, '../.run/catalog-mobile-redesign.png'), fullPage: true });
    const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 0) throw new Error(`Mobile horizontal overflow: ${overflow}px`);
    await mobile.close();
    if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
    console.log('Desktop, complete mobile navigation, readable history, auth tabs, posters, personal rating, favorite toggle, and account cleanup passed.');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
