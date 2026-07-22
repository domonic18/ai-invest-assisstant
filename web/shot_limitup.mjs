import { chromium } from 'playwright'

const base = 'http://localhost:9000'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 2400 } })

// login
await page.goto(`${base}/login`, { waitUntil: 'networkidle' })
const userInput = page.locator('input').first()
await userInput.fill(process.env.LOGIN_USER || 'admin')
await page.locator('input[type="password"]').fill(process.env.LOGIN_PASS || 'admin123')
await page.locator('button[type="submit"], button:has-text("登")').first().click()
await page.waitForURL((url) => !url.pathname.includes('login'), { timeout: 10000 })

// go to dashboard with trade date 2026-07-21 if date param exists
await page.goto(`${base}/?trade_date=2026-07-21`, { waitUntil: 'networkidle' })
await page.waitForTimeout(3000)
// try to set date via any date text if needed; just screenshot full page
await page.screenshot({ path: '/tmp/dashboard_0721.png', fullPage: true })
await browser.close()
console.log('done')
