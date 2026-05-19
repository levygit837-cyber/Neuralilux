sempre que for criar um teste, e executa-lo tenha certeza que o ambiente virtual está funcionando e usou o comando source venv/bin/activate. e quando realizar testes se faltar depêndencias instale via pip install -r requirements.txt


# Regras de Testes

## 1. Configuração do Ambiente
- Sempre execute os testes dentro do ambiente virtual ativado (`source venv/bin/activate`)
- Se faltarem dependências, instale-as com `pip install -r requirements.txt`

## 2. Execução dos Testes
- Use `python3 -m pytest tests/` para rodar todos os testes
- Use `python3 -m pytest tests/test_nome_do_arquivo.py -v` para testes específicos

## 3. Banco de Dados
- Testes que requerem banco de dados devem usar banco de dados em memória (SQLite)
- Não modifique o banco de dados de produção nos testes
- Use transações que são revertidas automaticamente ao final do teste

## 4. Mocking e Patches
- Use `pytest-mock` para mockar dependências externas (APIs, serviços externos)
- Mantenha os mocks isolados para cada teste
- Evite mockar código que você não controla diretamente (ex: bibliotecas de terceiros)

## 5. Testes de Integração
- Testes de integração devem testar fluxo completo entre componentes
- Use fixtures para configurar estado inicial comum
- Testes de integração devem ser mais lentos que testes unitários, mas ainda assim rápidos

## 6. Testes Unitários
- Testes unitários devem focar em uma única unidade de código
- Evite dependências externas desnecessárias
- Use mocks para isolar o código testado

## 7. Testes de Performance
- Testes de performance devem usar dados representativos
- Meça tempo de execução e uso de memória
- Evite testes que demorem mais de 1 segundo

## 8. Testes de Segurança
- Testes de segurança devem cobrir vulnerabilidades comuns
- Use ferramentas de análise estática de código
- Testes de segurança devem ser executados regularmente

## 9. Testes de UI
- Testes de UI devem usar ferramentas como Selenium ou Playwright
- Testes de UI devem ser executados em ambiente controlado
- Testes de UI devem ser executados em paralelo para economizar tempo

## 10. Testes de API
- Testes de API devem usar requisições HTTP reais
- Testes de API devem validar respostas JSON
- Testes de API devem cobrir todos os endpoints

## 11. Testes de Integração de Sistemas
- Testes de integração de sistemas devem testar fluxo completo entre sistemas
- Testes de integração de sistemas devem usar dados representativos
- Testes de integração de sistemas devem ser executados em ambiente controlado

## 12. Testes de Integração de Aplicações
- Testes de integração de aplicações devem testar fluxo completo entre aplicações
- Testes de integração de aplicações devem usar dados representativos
- Testes de integração de aplicações devem ser executados em ambiente controlado

## 13. Testes de Integração de Serviços
- Testes de integração de serviços devem testar fluxo completo entre serviços
- Testes de integração de serviços devem usar dados representativos
- Testes de integração de serviços devem ser executados em ambiente controlado

## 14. Testes de Integração de Componentes
- Testes de integração de componentes devem testar fluxo completo entre componentes
- Testes de integração de componentes devem usar dados representativos
- Testes de integração de componentes devem ser executados em ambiente controlado

## 15. Testes de Integração de Módulos
- Testes de integração de módulos devem testar fluxo completo entre módulos
- Testes de integração de módulos devem usar dados representativos
- Testes de integração de módulos devem ser executados em ambiente controlado

## 16. Testes de Integração de Pacotes
- Testes de integração de pacotes devem testar fluxo completo entre pacotes
- Testes de integração de pacotes devem usar dados representativos
- Testes de integração de pacotes devem ser executados em ambiente controlado

## 17. Testes de Integração de Dependências
- Testes de integração de dependências devem testar fluxo completo entre dependências
- Testes de integração de dependências devem usar dados representativos
- Testes de integração de dependências devem ser executados em ambiente controlado

## 18. Testes de Integração de Frameworks
- Testes de integração de frameworks devem testar fluxo completo entre frameworks
- Testes de integração de frameworks devem usar dados representativos
- Testes de integração de frameworks devem ser executados em ambiente controlado

## 19. Testes de Integração de Bibliotecas
- Testes de integração de bibliotecas devem testar fluxo completo entre bibliotecas
- Testes de integração de bibliotecas devem usar dados representativos
- Testes de integração de bibliotecas devem ser executados em ambiente controlado

## 20. Testes de Integração de Ferramentas
- Testes de integração de ferramentas devem testar fluxo completo entre ferramentas
- Testes de integração de ferramentas devem usar dados representativos
- Testes de integração de ferramentas devem ser executados em ambiente controlado

## 21. Testes de Integração de Protocolos
- Testes de integração de protocolos devem testar fluxo completo entre protocolos
- Testes de integração de protocolos devem usar dados representativos
- Testes de integração de protocolos devem ser executados em ambiente controlado

## 22. Testes de Integração de Padrões
- Testes de integração de padrões devem testar fluxo completo entre padrões
- Testes de integração de padrões devem usar dados representativos
- Testes de integração de padrões devem ser executados em ambiente controlado

## 23. Testes de Integração de Arquiteturas
- Testes de integração de arquiteturas devem testar fluxo completo entre arquiteturas
- Testes de integração de arquiteturas devem usar dados representativos
- Testes de integração de arquiteturas devem ser executados em ambiente controlado

## 24. Testes de Integração de Padrões de Projeto
- Testes de integração de padrões de projeto devem testar fluxo completo entre padrões de projeto
- Testes de integração de padrões de projeto devem usar dados representativos
- Testes de integração de padrões de projeto devem ser executados em ambiente controlado

## 25. Testes de Integração de Padrões de Design
- Testes de integração de padrões de design devem testar fluxo completo entre padrões de design
- Testes de integração de padrões de design devem usar dados representativos
- Testes de integração de padrões de design devem ser executados em ambiente controlado

## 26. Testes de Integração de Padrões de Arquitetura
- Testes de integração de padrões de arquitetura devem testar fluxo completo entre padrões de arquitetura
- Testes de integração de padrões de arquitetura devem usar dados representativos
- Testes de integração de padrões de arquitetura devem ser executados em ambiente controlado

## 27. Testes de Integração de Padrões de Design de Software
- Testes de integração de padrões de design de software devem testar fluxo completo entre padrões de design de software
- Testes de integração de padrões de design de software devem usar dados representativos
- Testes de integração de padrões de design de software devem ser executados em ambiente controlado

## 28. Testes de Integração de Padrões de Design de Aplicações
- Testes de integração de padrões de design de aplicações devem testar fluxo completo entre padrões de design de aplicações
- Testes de integração de padrões de design de aplicações devem usar dados representativos
- Testes de integração de padrões de design de aplicações devem ser executados em ambiente controlado

## 29. Testes de Integração de Padrões de Design de Sistemas
- Testes de integração de padrões de design de sistemas devem testar fluxo completo entre padrões de design de sistemas
- Testes de integração de padrões de design de sistemas devem usar dados representativos
- Testes de integração de padrões de design de sistemas devem ser executados em ambiente controlado

## 30. Testes de Integração de Padrões de Design de Arquiteturas
- Testes de integração de padrões de design de arquiteturas devem testar fluxo completo entre padrões de design de arquiteturas
- Testes de integração de padrões de design de arquiteturas devem usar dados representativos
- Testes de integração de padrões de design de arquiteturas devem ser executados em ambiente controlado