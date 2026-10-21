import nextVitals from 'eslint-config-next/core-web-vitals'

const config = [
  ...nextVitals,
  {
    rules: {
      '@next/next/no-img-element': 'off',
      // Regras novas do eslint-plugin-react-hooks 7 (React Compiler). Os padrões apontados
      // (fetch dentro de effect, timers recursivos com ref) funcionam hoje; reescrevê-los
      // sem teste de UI arrisca regressão. Reavaliar ao refatorar WhatsAppChat.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/immutability': 'warn',
    },
  },
]

export default config
