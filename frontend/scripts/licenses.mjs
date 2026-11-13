import { copyFileSync, mkdirSync, readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'

const destination = resolve('../beammpy/web/licenses')
mkdirSync(destination, { recursive: true })
copyFileSync(resolve('node_modules/@kyralabs/m3exp-web/LICENSE'), resolve(destination, 'M3E-Apache-2.0.txt'))
copyFileSync(resolve('node_modules/@kyralabs/m3e-tokens/fonts/LICENSE-google-sans-flex.txt'), resolve(destination, 'Google-Sans-Flex-OFL.txt'))
copyFileSync(resolve('node_modules/@kyralabs/m3e-tokens/fonts/LICENSE-material-symbols.txt'), resolve(destination, 'Material-Symbols-Apache-2.0.txt'))
copyFileSync(resolve('node_modules/@kyralabs/m3e-tokens/fonts/TRADEMARKS-google-sans-flex.md'), resolve(destination, 'Google-Sans-Flex-trademarks.md'))

// Include full notices for every shipped JS/CSS dependency, not just banner comments.
const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
for (const [directory, metadata] of Object.entries(lock.packages)) {
  if (!directory.startsWith('node_modules/') || metadata.dev) continue
  const name = directory.replace(/^node_modules\//, '').replaceAll('/', '_')
  for (const filename of readdirSync(directory)) {
    if (/^(license|copying|notice)(\.|$)/i.test(filename))
      copyFileSync(resolve(directory, filename), resolve(destination, name + '-' + filename))
  }
}
