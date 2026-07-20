const HEX6_PATTERN = /^#[0-9a-fA-F]{6}$/
const HEX8_PATTERN = /^#[0-9a-fA-F]{8}$/
const RGB_PATTERN = /^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/

/** 归一化为 6 位 hex 颜色；无法识别时原样返回，由后端校验报错。 */
export function normalizeHexColor(input: string): string {
  if (HEX6_PATTERN.test(input)) return input
  if (HEX8_PATTERN.test(input)) return input.slice(0, 7)
  const rgb = RGB_PATTERN.exec(input)
  if (rgb) {
    const channels = [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])]
    if (channels.every((v) => v <= 255)) {
      return `#${channels.map((v) => v.toString(16).padStart(2, '0')).join('')}`
    }
  }
  return input
}
