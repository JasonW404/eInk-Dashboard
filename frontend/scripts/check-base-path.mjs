import { readFileSync } from 'node:fs'

for (const page of ['index.html', 'eink.html']) {
  const html = readFileSync(new URL(`../dist/${page}`, import.meta.url), 'utf8')
  const references = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1])
  if (references.some((reference) => reference.startsWith('/assets/'))) {
    throw new Error(`${page} contains a root-absolute asset reference`)
  }
  if (!references.some((reference) => reference.startsWith('./assets/'))) {
    throw new Error(`${page} has no relative asset reference`)
  }
}

