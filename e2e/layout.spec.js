import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { writeFile } from 'node:fs/promises';

test('estados público e operacional: layout, acessibilidade e foco', async ({ page, request }, info) => {
  const health = await request.get('/health');
  expect(health.status()).toBe(200);
  expect((await health.json()).dependencies).toEqual({ store: true, risk: true });
  for (const [name, url] of [['home', '/'], ['login', '/operacao'], ['empty', '/empty-fixture'], ['degraded', '/degraded-fixture']]) {
    await page.goto(url);
    const width = await page.evaluate(() => ({ width: innerWidth, actual: document.documentElement.scrollWidth,
      overflow: [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > innerWidth + 1)
        .map(el => ({ tag: el.tagName, class: el.className, right: el.getBoundingClientRect().right })),
    }));
    await writeFile(info.outputPath(`layout-${name}.json`), JSON.stringify(width, null, 2));
    expect(width.actual, JSON.stringify(width)).toBeLessThanOrEqual(width.width);
    const result = await new AxeBuilder({ page }).analyze();
    await writeFile(info.outputPath(`axe-${name}.json`), JSON.stringify(result.violations, null, 2));
    expect(result.violations).toEqual([]);
    if (name === 'home') {
      await expect(page.locator('.zone.normal')).toContainText('simulado');
      await expect(page.locator('.zone.atencao')).toContainText('simulado');
      await expect(page.locator('.zone.alerta')).toContainText('simulado');
    } else if (name === 'degraded') {
      await expect(page.getByRole('status')).toContainText('DADOS TEMPORARIAMENTE INDISPONÍVEIS');
    }
    await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true });
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Pular para o conteúdo' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#conteudo')).toBeFocused();
  }
});
