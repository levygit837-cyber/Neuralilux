import nextVitals from 'eslint-config-next/core-web-vitals'
import jsxA11y from 'eslint-plugin-jsx-a11y'

// O eslint-config-next só liga 6 regras jsx-a11y; aqui entram as do conjunto recomendado como erro, com as opções
// de cada uma. As que o recomendado deixa desligadas (obsoletas ou ruidosas, como `label-has-for` e
// `anchor-ambiguous-text`) continuam desligadas.
const isOff = (setting) => {
  const level = Array.isArray(setting) ? setting[0] : setting
  return level === 'off' || level === 0
}

const recommended = Object.fromEntries(
  Object.entries(jsxA11y.flatConfigs.recommended.rules)
    .filter(([, setting]) => !isOff(setting))
    .map(([name, setting]) => [name, Array.isArray(setting) ? ['error', ...setting.slice(1)] : 'error'])
)

const config = [
  ...nextVitals,
  {
    files: ['**/*.{jsx,tsx}'],
    rules: {
      ...recommended,
      // depth 3: o texto do label costuma estar em <div><p> dentro do <label> (ex.: checkbox com descrição).
      'jsx-a11y/label-has-associated-control': ['error', { depth: 3 }],
      // Vem desligada no recomendado; é ela que acusa botão só com ícone e sem nome acessível.
      'jsx-a11y/control-has-associated-label': [
        'error',
        {
          ignoreElements: ['audio', 'canvas', 'embed', 'input', 'textarea', 'tr', 'video'],
          ignoreRoles: ['grid', 'listbox', 'menu', 'menubar', 'radiogroup', 'row', 'tablist', 'toolbar', 'tree', 'treegrid'],
          includeRoles: ['alert', 'dialog'],
          depth: 3,
        },
      ],
    },
  },
]

export default config
