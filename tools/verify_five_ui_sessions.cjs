/* Automated technical check of the four usability scenarios in five browser sessions. */
const { chromium } = require('playwright');
const { randomBytes } = require('crypto');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const runtime = path.join(root, '.run');
const port = JSON.parse(fs.readFileSync(path.join(runtime, 'processes.json'), 'utf8')).frontend_port;
const base = `http://localhost:${port}`;

async function main() {
  fs.mkdirSync(runtime, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const sessions = [];
  const accounts = [];
  try {
    for (let i = 0; i < 5; i++) {
      const context = await browser.newContext();
      const page = await context.newPage();
      page.setDefaultTimeout(10000);
      const email = `ui-check-${Date.now()}-${i}@example.com`;
      const password = randomBytes(18).toString('base64url');
      accounts.push({ email, password });
      const result = { session: i + 1, tasks: {} };
      try {
        await page.goto(base, { waitUntil: 'domcontentloaded' });
        await page.getByRole('tab', { name: 'Зареєструватися' }).click();
        await page.getByRole('textbox', { name: 'Email' }).fill(email);
        await page.getByRole('textbox', { name: 'Пароль' }).fill(password);
        await page.getByRole('button', { name: 'Створити обліковий запис' }).click();
        await page.getByText('Реєстрацію завершено. Тепер увійдіть.').waitFor();
        await page.getByRole('button', { name: 'Увійти →' }).click();
        await page.getByRole('button', { name: 'Профіль' }).waitFor();

        let started = Date.now();
        await page.getByRole('textbox', { name: 'Назва або ключове слово' }).fill('Demo Orbit');
        await page.getByRole('button', { name: 'Відкрити Demo Orbit' }).click();
        await page.getByRole('heading', { name: 'Demo Orbit' }).waitFor();
        result.tasks.find_movie_ms = Date.now() - started;

        started = Date.now();
        await Promise.all([
          page.waitForResponse((response) => response.url().includes('/me/watchlist/') && response.request().method() === 'PUT' && response.status() === 200),
          page.getByRole('button', { name: /До перегляду/ }).click(),
        ]);
        await page.getByRole('status').getByText('Зміни збережено').waitFor();
        result.tasks.add_watchlist_ms = Date.now() - started;

        started = Date.now();
        await Promise.all([
          page.waitForResponse((response) => response.url().includes('/me/ratings/') && response.request().method() === 'PUT' && response.status() === 200),
          page.getByRole('button', { name: 'Оцінити на 5 з 5' }).click(),
        ]);
        result.tasks.rate_movie_ms = Date.now() - started;

        started = Date.now();
        await page.getByRole('button', { name: 'Для вас' }).click();
        await page.getByRole('heading', { name: 'Для вас' }).waitFor();
        await page.locator('.poster-grid article').first().waitFor();
        result.tasks.open_recommendations_ms = Date.now() - started;
        result.recommendation_cards = await page.locator('.poster-grid article').count();
        result.success = result.recommendation_cards > 0;
        if (i === 0) await page.screenshot({ path: path.join(runtime, 'ui-check-recommendations.png'), fullPage: true });
        await page.getByRole('button', { name: 'Профіль' }).click();
        await page.getByRole('textbox', { name: 'Пароль для видалення' }).fill(password);
        await page.getByRole('textbox', { name: 'Підтвердження DELETE' }).fill('DELETE');
        await page.getByRole('button', { name: 'Видалити профіль' }).click();
        await page.getByText('Обліковий запис видалено').waitFor();
      } catch (error) {
        result.success = false;
        result.error = String(error);
      }
      sessions.push(result);
      await context.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(runtime, 'ui-test-accounts.json'), JSON.stringify(accounts, null, 2));
  const report = { kind: 'automated_browser_check_not_human_usability_study', sessions };
  fs.writeFileSync(path.join(runtime, 'five-ui-sessions.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  if (sessions.some((session) => !session.success)) process.exitCode = 1;
}

main().catch((error) => { console.error(String(error)); process.exitCode = 1; });
