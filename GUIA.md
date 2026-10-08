# Bot de ofertas de trabajo — @tcm.uruguay y @__b.t.u__

Cada hora, este bot:

1. Busca en Instagram las publicaciones **más recientes** (últimas 24 h) con hashtags de empleo en Uruguay (`#trabajouruguay`, `#empleomontevideo`, etc.).
2. Se queda solo con las que son **búsquedas laborales de empresas**. Descarta estafas ("ganá dinero desde tu casa", cripto…), personas que buscan trabajo y tus propios posts.
3. Genera una **tarjeta con tu estilo**: puesto, zona y cómo postularse.
4. Publica una oferta **distinta** en cada cuenta, con la descripción de la empresa y el link al post original.
5. No repite ofertas y, si en esa hora no hay ninguna nueva, no publica nada.

Corre gratis en **GitHub Actions**: tu computadora puede estar apagada.

---

## Paso 1 — Preparar las cuentas de Instagram (5 min)

Hacé esto en **cada** cuenta (@tcm.uruguay y @__b.t.u__):

1. En Instagram: **Configuración → Tipo de cuenta y herramientas → Cambiar a cuenta profesional** (Empresa o Creador).
2. Vinculá la cuenta a una **página de Facebook**: *Editar perfil → Página*. Puede ser una página distinta para cada cuenta.
3. Ambas páginas tienen que estar en el mismo **portfolio comercial** de Meta. Revisalo en [business.facebook.com](https://business.facebook.com) → *Configuración → Cuentas → Páginas* y *Cuentas de Instagram*.

## Paso 2 — Crear la app de Meta (10 min, gratis)

1. Entrá a [developers.facebook.com](https://developers.facebook.com) → **Mis apps → Crear app**.
2. Caso de uso: **Otro** → tipo **Empresa**. Asociala a tu portfolio comercial.
3. En la app, agregá el producto **Instagram** → *Configuración de la API con inicio de sesión con Facebook*.
4. Dejá la app en **modo desarrollo**. Como las cuentas son tuyas, no hace falta la revisión de Meta.

## Paso 3 — Crear el token que no vence (5 min)

1. En [business.facebook.com](https://business.facebook.com) → **Configuración → Usuarios → Usuarios del sistema → Agregar**. Nombre: `bot-empleos`, rol **Administrador**.
2. **Asignar activos**: las 2 páginas y las 2 cuentas de Instagram (control total) y tu app.
3. **Generar token**:
   - App: la que creaste.
   - Caducidad: **Nunca**.
   - Permisos: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
4. Copiá el token. **No lo compartas con nadie ni lo pegues en ningún archivo**: va solo en los secretos de GitHub (paso 4).

## Paso 4 — Subir el bot a GitHub (10 min, gratis)

1. Creá una cuenta en [github.com](https://github.com) si no tenés.
2. Creá un repositorio **público** llamado `bot-empleos` y subí todos estos archivos. Tiene que ser público para que Instagram pueda descargar las tarjetas. El token **no** queda visible.
3. En el repositorio: **Settings → Secrets and variables → Actions → New repository secret** y creá:
   - `IG_TOKEN` → el token del paso 3.
4. Pestaña **Actions** → si pregunta, activá los workflows.
5. Ejecutá **"Ver IDs de mis cuentas" → Run workflow**. Al terminar, abrí el resultado y vas a ver algo así:
   ```
   Página 'TCM Uruguay' → @tcm.uruguay  ID: 1784…
   Página 'BTU' → @__b.t.u__  ID: 1784…
   ```
6. Creá dos secretos más con esos números: `IG_ID_TCM` e `IG_ID_BTU`.

## Paso 5 — Probar y encender

1. **Actions → "Publicar ofertas de trabajo" → Run workflow → modo `sin-publicar`.** Busca ofertas reales y genera las tarjetas sin publicarlas. Mirá cómo quedaron en la carpeta `publicadas/` del repositorio.
2. Si te gustan: **Run workflow → modo `publicar`**. Revisá que aparezcan en tus cuentas.
3. Listo. Desde ahí corre **solo, cada hora**, todos los días.

---

## Cómo cambiar cosas

| Quiero… | Dónde |
|---|---|
| Cambiar la frecuencia | `.github/workflows/publicar.yml`, línea `cron`. `"0 * * * *"` = cada hora; `"0 */2 * * *"` = cada 2 horas; `"0 9-21 * * *"` = solo de 6 a 18 h de Uruguay (UTC-3) |
| Usar mi logo real | Subí `assets/logo_tcm.png` y `assets/logo_btu.png` (cuadrados) |
| Cambiar colores o el lema | `config.json` → `color_fondo`, `color_texto`, `lema` |
| Buscar en otros hashtags | `config.json` → `hashtags_a_buscar` (máximo 30 distintos por semana, es límite de Instagram) |
| Filtrar más estafas | `config.json` → `palabras_prohibidas` |
| Cambiar los hashtags que se publican | `config.json` → `hashtags_al_publicar` |
| Pausar el bot | Actions → "Publicar ofertas de trabajo" → `···` → **Disable workflow** |

## Cosas a saber

- **Solo encuentra posts con hashtags.** La API oficial de Instagram no permite otro tipo de búsqueda. Si una empresa no usa hashtags de empleo, el bot no la ve.
- **Instagram no informa qué cuenta subió el post** en las búsquedas por hashtag. Por eso el crédito se da con el **link a la publicación original** en la descripción.
- El puesto se detecta automáticamente desde el texto de la empresa. A veces puede quedar genérico ("PERSONAL") o un poco largo.
- GitHub puede demorar unos minutos el horario exacto de cada ejecución.
- Si algo falla, GitHub te manda un mail y en **Actions** ves el detalle en rojo.
- Para ver tarjetas de ejemplo sin internet: `python bot.py --prueba` (quedan en `vista_previa/`).
