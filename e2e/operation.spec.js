import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { writeFile } from 'node:fs/promises';

test('login, medição, boletim e logout em três processos HTTP', async ({ page }, info) => {
  await page.goto('/operacao');
  await page.getByLabel('Senha operacional').fill('fixture-operator-only');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Registrar medição' })).toBeVisible();
  const audit = await new AxeBuilder({ page }).analyze();
  await writeFile(info.outputPath('axe-authenticated.json'), JSON.stringify(audit.violations, null, 2));
  expect(audit.violations).toEqual([]);
  const measurement = page.getByRole('region', { name: 'Registrar medição' });
  await measurement.getByRole('combobox', { name: /^Zona/ }).selectOption('Central');
  await measurement.getByLabel('Temperatura °C').fill('30');
  await measurement.getByLabel('Umidade %').fill('60');
  await measurement.getByRole('button', { name: 'Avaliar e registrar' }).click();
  await expect(page.getByRole('status')).toContainText('Medição avaliada e registrada.');
  const bulletin = page.getByRole('region', { name: 'Publicar boletim' });
  const title = `Boletim sintético ${info.project.name}`;
  await bulletin.getByLabel('Título', { exact: true }).fill(title);
  await bulletin.getByLabel('Orientação', { exact: true }).fill('Fixture de teste; nenhum comunicado real.');
  await bulletin.getByRole('button', { name: 'Publicar orientação' }).click();
  await expect(page.getByRole('status')).toContainText('Boletim publicado.');
  await page.getByRole('button', { name: 'Sair da operação' }).click();
  await expect(page.getByRole('heading', { name: title })).toBeVisible();
  await page.goto('/operacao');
  await expect(page.getByLabel('Senha operacional')).toBeVisible();
});

test('login e navegação pública funcionam sem JavaScript', async ({ browser }, info) => {
  const context = await browser.newContext({ ...info.project.use, javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('/operacao');
  await page.getByLabel('Senha operacional').fill('fixture-operator-only');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Registrar medição' })).toBeVisible();
  await page.getByRole('button', { name: 'Sair da operação' }).click();
  await expect(page.getByRole('heading', { name: 'Situação por zona' })).toBeVisible();
  await context.close();
});
