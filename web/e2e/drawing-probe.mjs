// 临时探针：诊断指数页 canvas 未出现。用完即删。
import { chromium } from 'playwright'

const BASE = 'http://localhost:9000'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('response', (res) => {
  if (res.url().includes('kline')) {
    console.log(`${res.request().method()} ${res.url().replace(BASE, '')} -> ${res.status()}`)
  }
})
await page.goto(`${BASE}/login`)
await page.fill('input[id="login_username"]', 'testuser')
await page.fill('input[id="login_password"]', 'secret123')
await page.click('button[type="submit"]')
await page.waitForURL(`${BASE}/**`, { timeout: 10000 })
await page.goto(`${BASE}/index/000001`)
await page.waitForTimeout(6000)
console.log('url:', page.url())
console.log('canvas count:', await page.locator('canvas').count())
console.log('画线按钮:', await page.locator('button[title="画线工具"]').count())
console.log((await page.locator('body').innerText()).slice(0, 600).replace(/\n+/g, ' | '))
await page.screenshot({ path: '/tmp/probe-index.png', fullPage: true })
await browser.close()
