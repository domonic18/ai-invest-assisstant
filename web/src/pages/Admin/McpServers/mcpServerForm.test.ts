import { describe, expect, it } from 'vitest'

import { parseMcpConfigJson } from './mcpServerForm'

describe('parseMcpConfigJson', () => {
  it('解析标准 mcpServers 形状并取第一个 server', () => {
    const cfg = parseMcpConfigJson(
      JSON.stringify({
        mcpServers: {
          squadsight: {
            url: 'https://sight.example.com/mcp',
            headers: { Authorization: 'Bearer sk-xxx' },
          },
        },
      }),
    )
    expect(cfg.name).toBe('squadsight')
    expect(cfg.transportType).toBe('http')
    expect(cfg.url).toBe('https://sight.example.com/mcp')
    expect(cfg.headers).toEqual({ Authorization: 'Bearer sk-xxx' })
  })

  it('解析 stdio 形状（command/args/env）', () => {
    const cfg = parseMcpConfigJson(
      JSON.stringify({
        mcpServers: {
          fs: { command: 'npx', args: ['-y', '@modelcontextprotocol/server-fs'], env: { A: '1' } },
        },
      }),
    )
    expect(cfg.transportType).toBe('stdio')
    expect(cfg.command).toBe('npx')
    expect(cfg.args).toEqual(['-y', '@modelcontextprotocol/server-fs'])
    expect(cfg.env).toEqual({ A: '1' })
  })

  it('支持无 mcpServers 包装的单 server 对象与 type 声明', () => {
    const cfg = parseMcpConfigJson(JSON.stringify({ url: 'https://x/mcp', type: 'sse' }))
    expect(cfg.transportType).toBe('sse')
    expect(cfg.url).toBe('https://x/mcp')
  })

  it('非法 JSON 抛错', () => {
    expect(() => parseMcpConfigJson('{not json')).toThrow('JSON')
  })

  it('缺少 url 与 command 时抛错', () => {
    expect(() => parseMcpConfigJson(JSON.stringify({ mcpServers: { a: {} } }))).toThrow(
      '传输通道',
    )
  })
})
