import nextVitals from 'eslint-config-next/core-web-vitals'
import jsxA11y from 'eslint-plugin-jsx-a11y'

// O eslint-config-next só liga 6 regras jsx-a11y; aqui entra o conjunto recomendado completo como erro.
// `label-has-for` está obsoleta (exige aninhamento E id ao mesmo tempo); `label-has-associated-control` a substitui.
const recommended = Object.fromEntries(
  Object.entries(jsxA11y.flatConfigs.recommended.rules).map(([name, setting]) => [
    name,
    Array.isArray(setting) ? ['error', ...setting.slice(1)] : 'error',
  ])
)

const config = [
  ...nextVitals,
  {
    files: ['**/*.{jsx,tsx}'],
    rules: {
      ...recommended,
      'jsx-a11y/label-has-for': 'off',
      // depth 3: o texto do label costuma estar em <div><p> dentro do <label> (ex.: checkbox com descrição).
      'jsx-a11y/label-has-associated-control': ['error', { depth: 3 }],
    },
  },
]

export default config
