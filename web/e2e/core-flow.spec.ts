import { expect, test } from '@playwright/test'

test('login -> dashboard -> chain -> stock flow', async ({ page }) => {
  await page.goto('/login')
  await page.fill('input[id="login_username"]', 'testuser')
  await page.fill('input[id="login_password"]', 'secret123')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/')

  await page.click('text=产业链分析')
  await expect(page).toHaveURL(/\/chain/)
  await page.click('button:has-text("AI 分析")')
  await expect(page.getByText('产业链关系图谱')).toBeVisible()

  await page.fill('input[placeholder="搜索股票代码/名称"]', '000001')
  await page.click('.ant-select-item-option-content:has-text("平安银行")')
  await expect(page).toHaveURL(/\/stock\/000001/)
  await expect(page.getByText('K线分析')).toBeVisible()
})
