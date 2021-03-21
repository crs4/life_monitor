import { babel } from '@rollup/plugin-babel';

const pkg = require('../package')
const year = new Date().getFullYear()

const globals = {
  jquery: 'jQuery'
}

export default {
  input: 'js/lifemonitor.js',
  output: {
    banner: `/*!
 * LifeMonitor v${pkg.version} (${pkg.homepage})
 * Copyright 2020-${year} ${pkg.author}
 * Licensed under MIT
 */`,
    file: '../dist/js/lifemonitor.js',
    format: 'umd',
    globals,
    name: 'lifemonitor'
  },
  plugins: [babel({
    babelHelpers: 'bundled',
    exclude: 'node_modules/**'
  })]
}
