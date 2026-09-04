import { expect, test } from '@playwright/test'

test('register and login flow', async ({ page }) => {
  const username = `e2e_${Date.now()}`
  const email = `${username}@example.com`

  await page.goto('/register')
  await page.fill('input[id="register_username"]', username)
  await page.fill('input[id="register_email"]', email)
  await page.fill('input[id="register_password"]', 'secret123')
  await page.fill('input[id="register_confirmPassword"]', 'secret123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL('/')
  await expect(page.getByText(username)).toBeVisible()
})

test('login with existing user', async ({ page }) => {
  await page.goto('/login')
  await page.fill('input[id="login_username"]', 'testuser')
  await page.fill('input[id="login_password"]', 'secret123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL('/')
  await expect(page.getByText('仪表盘')).toBeVisible()
})
