import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const runtimeConfig = readFileSync('public/runtime-config.js', 'utf8')

runInNewContext(runtimeConfig, { window })
