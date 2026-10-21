# Núcleo genérico e Packs por Business Type

Loop, memória, prompts base e registry de Tools não conhecem nenhum ramo. Tudo que é de restaurante (Catalog Item, Order, Delivery Zone, Pix) vive no Pack "catálogo & pedidos" em `backend/app/packs/catalog_orders/`. Um novo ramo (farmácia, loja, academia) entra como outro Pack, sem tocar no núcleo. O `company_id` de toda Tool vem da Instance, nunca de `Company.first()` ou de nome fixo.
