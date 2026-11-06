import { expect, test } from '@playwright/test';

type ContrastSample = { link: string; progress: number; foreground: string; background: number[]; ratio: number; animations: number };
type ContrastWindow = Window & { navigationContrast?: ContrastSample[] };

for (const theme of ['light', 'dark']) {
  test(`incoming and outgoing navigation text retain contrast throughout selection in ${theme}`, async ({ page }, testInfo) => {
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.goto('/');
    await page.getByRole('combobox', { name: 'Farbschema', exact: true }).selectOption(theme);
    const samples: ContrastSample[] = [];

    for (const target of ['Fälle', 'Versuche', 'PDF-Quellen']) {
      const next = page.getByRole('link', { name: target, exact: true });
      await next.hover();
      await next.focus();
      await page.evaluate(async (label) => {
        const rgba = (value: string) => {
          const channels = value.match(/[\d.]+/g)!.map(Number);
          return [channels[0], channels[1], channels[2], channels[3] ?? 1];
        };
        const composite = (front: number[], back: number[]) => front.slice(0, 3)
          .map((channel, index) => channel * front[3] + back[index] * (1 - front[3]));
        const luminance = (color: number[]) => color.map(channel => {
          const value = channel / 255;
          return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
        }).reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0);
        const measure = (link: HTMLAnchorElement, progress: number): ContrastSample => {
          const ancestors: Element[] = [];
          for (let element: Element | null = link; element; element = element.parentElement) ancestors.unshift(element);
          const background = ancestors.reduce((back, element) => composite(rgba(getComputedStyle(element).backgroundColor), back), [255, 255, 255]);
          const foreground = getComputedStyle(link).color;
          const fg = luminance(composite(rgba(foreground), background));
          const bg = luminance(background);
          return { link: link.textContent!.trim(), progress, foreground, background,
            ratio: (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05), animations: link.getAnimations().length };
        };
        const links = [...document.querySelectorAll<HTMLAnchorElement>('.sidebar nav a')];
        const incoming = links.find(link => link.textContent?.trim() === label)!;
        const outgoing = links.find(link => link.classList.contains('active'))!;
        const changing = [outgoing, incoming];
        // Start from the actual hover/focus endpoint, then inspect the entire
        // active/inactive transition instead of waiting for it to finish.
        await Promise.all(changing.flatMap(link => link.getAnimations()).map(animation => animation.finished));
        (window as ContrastWindow).navigationContrast = undefined;
        const observer = new MutationObserver(() => {
          if (!incoming.classList.contains('active') || outgoing.classList.contains('active')) return;
          observer.disconnect();
          changing.forEach(link => getComputedStyle(link).color);
          const animations = changing.flatMap(link => link.getAnimations());
          animations.forEach(animation => animation.pause());
          const captured = [0, 0.25, 0.5, 0.75, 1].flatMap(progress => {
            animations.forEach(animation => {
              const duration = Number(animation.effect?.getComputedTiming().duration ?? 0);
              animation.currentTime = duration * progress;
            });
            return changing.map(link => measure(link, progress));
          });
          animations.forEach(animation => animation.finish());
          (window as ContrastWindow).navigationContrast = captured;
        });
        observer.observe(incoming.parentElement!, { attributes: true, subtree: true, attributeFilter: ['class', 'aria-current'] });
      }, target);
      await next.click();
      await expect(next).toHaveAttribute('aria-current', 'page');
      await expect.poll(() => page.evaluate(() => (window as ContrastWindow).navigationContrast?.length)).toBe(10);
      samples.push(...await page.evaluate(() => (window as ContrastWindow).navigationContrast!));
    }

    await testInfo.attach(`navigation-contrast-${theme}`, { body: JSON.stringify(samples, null, 2), contentType: 'application/json' });
    expect(samples.filter(sample => sample.ratio < 4.5), 'Normal-sized navigation text must retain WCAG AA contrast at every sampled transition point.').toEqual([]);
  });
}
