/* Browser check of search, profile editing, and demo account roles. */
const { chromium } = require('playwright');
const { randomBytes } = require('crypto');
const fs = require('fs');
const path = require('path');

async function main() {
  const root = path.resolve(__dirname, '..');
  const port = JSON.parse(fs.readFileSync(path.join(root, '.run/processes.json'), 'utf8')).frontend_port;
  const credentials = fs.readFileSync(path.join(root, 'TEST_ACCOUNTS.txt'), 'utf8');
  const demoAccounts = [...credentials.matchAll(/Роль: (admin|user)\r?\nEmail: ([^\r\n]+)\r?\nПароль: ([^\r\n]+)/g)].map(([, role, email, password]) => ({ role, email, password }));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  const email = `updated-${Date.now()}@example.com`;
  const changedEmail = `changed-${Date.now()}@example.com`;
  const password = randomBytes(18).toString('base64url');
  const changedPassword = randomBytes(18).toString('base64url');
  let validationResponses = 0;
  page.on('response', response => { if (response.status() === 422) validationResponses++; });
  try {
    await page.goto(`http://localhost:${port}`, { waitUntil: 'networkidle' });
    await page.getByRole('spinbutton', { name: 'Рік від' }).fill('-30');
    await page.getByRole('alert').getByText('Рік має бути цілим числом від 1888 до 2200.').waitFor();
    await page.getByRole('spinbutton', { name: 'Рік від' }).fill('');
    await page.getByRole('textbox', { name: 'Назва або ключове слово' }).fill('Interstellar');
    await page.getByRole('spinbutton', { name: 'Рік від' }).fill('2010');
    await page.getByRole('spinbutton', { name: 'Рік до' }).fill('2020');
    await page.getByRole('spinbutton', { name: 'Мінімальний рейтинг від 0 до 10' }).fill('7');
    await page.getByRole('button', { name: 'Відкрити Interstellar' }).waitFor();
    if (await page.locator('.poster-grid article').count() !== 1) throw new Error('Search filters returned an unexpected number of movies');

    await page.getByRole('tab', { name: 'Зареєструватися' }).click();
    await page.getByRole('textbox', { name: 'Email' }).fill(email);
    await page.getByRole('textbox', { name: 'Пароль' }).fill(password);
    await page.getByRole('button', { name: 'Створити обліковий запис' }).click();
    await page.getByText('Реєстрацію завершено. Тепер увійдіть.').waitFor();
    await page.getByRole('button', { name: 'Увійти →' }).click();
    await page.getByRole('button', { name: 'Профіль' }).click();
    await page.getByRole('textbox', { name: 'Новий email' }).fill(changedEmail);
    const [emailResponse] = await Promise.all([page.waitForResponse(response => response.url().includes('/me/email')), page.getByRole('button', { name: 'Зберегти email' }).click()]);
    if (emailResponse.status() !== 200) throw new Error(`Email update failed: ${emailResponse.status()}`);
    await page.getByRole('textbox', { name: 'Поточний пароль' }).fill(password);
    await page.getByRole('textbox', { name: 'Новий пароль' }).fill(changedPassword);
    const [passwordResponse] = await Promise.all([page.waitForResponse(response => response.url().includes('/me/password')), page.getByRole('button', { name: 'Змінити пароль' }).click()]);
    if (passwordResponse.status() !== 204) throw new Error(`Password update failed: ${passwordResponse.status()}`);
    await page.getByRole('textbox', { name: 'Поточний пароль' }).waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.querySelector('input[aria-label="Поточний пароль"]')?.value === '');
    await page.getByRole('textbox', { name: 'Пароль для видалення' }).fill(changedPassword);
    await page.getByRole('textbox', { name: 'Підтвердження DELETE' }).fill('DELETE');
    const [deleteResponse] = await Promise.all([page.waitForResponse(response => response.url().includes('/me/account')), page.getByRole('button', { name: 'Видалити профіль' }).click()]);
    if (deleteResponse.status() !== 204) throw new Error(`Account deletion failed: ${deleteResponse.status()} ${await deleteResponse.text()}`);
    await page.getByText('Обліковий запис видалено').waitFor();
    await page.getByRole('tab', { name: 'Увійти' }).click();
    await page.getByRole('textbox', { name: 'Email' }).fill(changedEmail);
    await page.getByRole('textbox', { name: 'Пароль' }).fill(changedPassword);
    await page.getByRole('button', { name: 'Увійти →' }).click();
    await page.getByText('Неправильний email або пароль.').waitFor();
    if (demoAccounts.length !== 2) throw new Error('Demo credentials are missing');
    for (const account of demoAccounts) {
      await page.getByRole('textbox', { name: 'Email' }).fill(account.email);
      await page.getByRole('textbox', { name: 'Пароль' }).fill(account.password);
      await page.getByRole('button', { name: 'Увійти →' }).click();
      await page.getByText(account.role === 'admin' ? 'Адміністратор' : 'Глядач').waitFor();
      if (account.role === 'admin') {
        await page.getByRole('button', { name: 'Адмін' }).click();
        await page.getByRole('heading', { name: 'Додати фільм' }).waitFor();
        await page.getByRole('textbox', { name: 'Зовнішній ID' }).waitFor();
        await page.getByRole('textbox', { name: 'Актори' }).waitFor();
        await page.getByRole('textbox', { name: 'Режисери' }).waitFor();
      }
      await page.getByRole('button', { name: 'Вийти' }).click();
      await page.getByRole('tab', { name: 'Увійти' }).click();
    }
    if (validationResponses !== 0) throw new Error(`Unexpected 422 responses: ${validationResponses}`);
    console.log('Search validation, profile changes, complete admin movie fields, and both demo accounts passed.');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
