// Archivo: static/menu/menu.js

function menuApp() {
    return {
        tab: "categorias",
        categorias: [],
        platos: [],
        insumosDisponibles: [],
        insumosCriticos: [],
        filtroCategoriaPlatos: "",
        busquedaPlato: "",
        busquedaCategoria: "",
        busquedaInsumo: "",
        guardandoPlato: false,
        cargandoPlatoId: null,
        erroresPlato: {},
        imagenPreview: "",
        mensajeExito: "",
        mensajeAviso: "",

        modalCategoriaInst: null,
        modalPlatoInst: null,
        modalEliminarCategoriaInst: null,
        modalEliminarPlatoInst: null,
        modalErrorInst: null,
        mensajeError: "",

        categoriaForm: {
            id: null,
            nombre: "",
            icono: "",
            orden: 0,
            activo: true,
        },
        categoriaEliminarId: null,
        categoriaEliminarNombre: "",
        categoriaEliminarMensaje: "Si tiene platos asociados, no se podrá eliminar.",

        platoForm: {
            id: null,
            categoria: "",
            nombre: "",
            descripcion: "",
            precio_actual: 0.0,
            tiempo_preparacion_min: 0,
            disponible: true,
            activo: true,
            recetas: [],
            motivo: "",
        },
        platoOriginal: null,
        platoEliminarId: null,
        platoEliminarNombre: "",
        platoEliminarMotivo: "",
        platoEliminarError: "",
        eliminandoPlato: false,

        newInsumoId: "",

        platosPaginacion: {
            paginaActual: 1,
            porPagina: 5,
            totalPaginas: 1,
        },
        categoriasPaginacion: {
            paginaActual: 1,
            porPagina: 5,
        },

        get categoriasFiltradas() {
            const termino = (this.busquedaCategoria || "")
                .trim()
                .toLowerCase()
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "");
            if (!termino) return this.categorias;
            return this.categorias.filter((categoria) =>
                (categoria.nombre || "")
                    .toLowerCase()
                    .normalize("NFD")
                    .replace(/[\u0300-\u036f]/g, "")
                    .includes(termino)
            );
        },

        get categoriasPaginadas() {
            const totalPaginas = Math.max(
                1,
                Math.ceil(this.categoriasFiltradas.length / this.categoriasPaginacion.porPagina)
            );
            if (this.categoriasPaginacion.paginaActual > totalPaginas) {
                this.categoriasPaginacion.paginaActual = totalPaginas;
            }
            const inicio = (
                this.categoriasPaginacion.paginaActual - 1
            ) * this.categoriasPaginacion.porPagina;
            return this.categoriasFiltradas.slice(
                inicio,
                inicio + this.categoriasPaginacion.porPagina
            );
        },

        get totalPaginasCategorias() {
            return Math.max(
                1,
                Math.ceil(this.categoriasFiltradas.length / this.categoriasPaginacion.porPagina)
            );
        },

        get platosFiltrados() {
            let lista = this.platos;
            if (this.filtroCategoriaPlatos) {
                lista = lista.filter(p => p.categoria == this.filtroCategoriaPlatos);
            }

            if ((this.busquedaPlato || '').trim() !== "") {
                const termino = this.busquedaPlato.toLowerCase();
                lista = lista.filter(p => (p.nombre || '').toLowerCase().includes(termino));
            }

            this.platosPaginacion.totalPaginas = Math.ceil(lista.length / this.platosPaginacion.porPagina) || 1;

            const inicio = (this.platosPaginacion.paginaActual - 1) * this.platosPaginacion.porPagina;
            const fin = inicio + this.platosPaginacion.porPagina;

            return lista.slice(inicio, fin);
        },

        get insumosFiltrados() {
            const termino = (this.busquedaInsumo || "").trim().toLowerCase();
            const usados = new Set((this.platoForm.recetas || []).map((r) => Number(r.insumo_id)));
            return (this.insumosDisponibles || [])
                .filter((insumo) => insumo && insumo.id && !usados.has(Number(insumo.id)))
                .filter((insumo) => !termino || (insumo.nombre || "").toLowerCase().includes(termino));
        },

        get requiereMotivoPlato() {
            if (!this.platoForm.id || !this.platoOriginal) return false;
            return this.estadoCriticoPlato(this.platoOriginal)
                !== this.estadoCriticoPlato(this.platoForm);
        },

        get porcionesDisponiblesPlato() {
            const recetas = (this.platoForm.recetas || []).filter((r) => Number(r.cantidad_por_porcion) > 0);
            if (!recetas.length) return 0;
            return Math.max(0, Math.min(...recetas.map((receta) =>
                Math.floor(Number(receta.insumo_stock || 0) / this.cantidadEnUnidadControl(receta))
            )));
        },

        init() {
            this.modalCategoriaInst = new bootstrap.Modal(document.getElementById("modalCategoria"));
            this.modalPlatoInst = new bootstrap.Modal(document.getElementById("modalPlato"));
            this.modalEliminarCategoriaInst = new bootstrap.Modal(document.getElementById("modalEliminarCategoria"));
            this.modalEliminarPlatoInst = new bootstrap.Modal(document.getElementById("modalEliminarPlato"));
            this.modalErrorInst = new bootstrap.Modal(document.getElementById("modalError"));
            this.fetchCategorias();
            this.fetchPlatos();
            this.fetchInsumosDisponibles();
            this.fetchInsumoCriticos();
        },

        mostrarError(mensaje) {
            this.mensajeError = mensaje;
            this.modalErrorInst.show();
            setTimeout(() => {
                const backdrops = document.querySelectorAll(".modal-backdrop");
                if (backdrops.length > 0) {
                    backdrops[backdrops.length - 1].style.zIndex = "1074";
                }
                const el = document.getElementById("modalError");
                if (el) el.style.zIndex = "1075";
            }, 10);
        },

        mostrarExito(mensaje) {
            this.mensajeExito = mensaje;
            window.clearTimeout(this._mensajeExitoTimer);
            this._mensajeExitoTimer = window.setTimeout(() => {
                this.mensajeExito = "";
            }, 3500);
        },

        mostrarAvisoMotivo() {
            this.mensajeAviso = "Antes de guardar, indica el motivo del cambio importante.";
            window.setTimeout(() => {
                const campo = document.getElementById("motivoCambioPlato");
                if (!campo) return;
                campo.scrollIntoView({ behavior: "smooth", block: "center" });
                campo.focus({ preventScroll: true });
            }, 80);
        },

        recetaNormalizada(recetas) {
            return JSON.stringify((recetas || [])
                .filter((item) => item.activo !== false)
                .map((item) => ({
                    insumo_id: Number(item.insumo_id),
                    cantidad: Number(item.cantidad_por_porcion),
                    unidad_medida_id: Number(item.unidad_medida_id),
                    merma: Number(item.merma_porcentaje || 0),
                }))
                .sort((a, b) => a.insumo_id - b.insumo_id));
        },

        estadoPlatoNormalizado(plato) {
            const recetas = plato.recetas || plato.receta || [];
            return JSON.stringify({
                nombre: (plato.nombre || "").trim(),
                descripcion: (plato.descripcion || "").trim(),
                categoria: Number(plato.categoria || 0),
                precio_actual: Number(plato.precio_actual || 0),
                tiempo_preparacion_min: Number(plato.tiempo_preparacion_min || 0),
                disponible: Boolean(plato.disponible),
                activo: Boolean(plato.activo),
                imagen: plato.nueva_imagen ? "__nueva_imagen__" : (plato.imagen_url || ""),
                receta: this.recetaNormalizada(recetas),
            });
        },

        estadoCriticoPlato(plato) {
            const recetas = plato.recetas || plato.receta || [];
            return JSON.stringify({
                precio_actual: Number(plato.precio_actual || 0),
                disponible: Boolean(plato.disponible),
                activo: Boolean(plato.activo),
                receta: this.recetaNormalizada(recetas),
            });
        },

        esUnidadDiscreta(receta) {
            const unidad = this.unidadReceta(receta);
            return unidad ? Boolean(unidad.es_discreta) : Boolean(receta.insumo_es_discreto);
        },

        unidadReceta(receta) {
            return (receta.unidades_compatibles || []).find(
                (unidad) => Number(unidad.id) === Number(receta.unidad_medida_id)
            ) || null;
        },

        cambiarUnidadReceta(receta) {
            const unidad = this.unidadReceta(receta);
            receta.insumo_unidad = unidad ? unidad.simbolo : "";
            receta.insumo_es_discreto = unidad ? Boolean(unidad.es_discreta) : false;
            this.normalizarCantidadReceta(receta);
        },

        cantidadEnUnidadControl(receta) {
            const unidad = this.unidadReceta(receta);
            const factorSeleccionado = Number(unidad?.factor_conversion || 1);
            const factorControl = Number(receta.unidad_control_factor || 1);
            const cantidad = Number(receta.cantidad_por_porcion || 0);
            return Math.max(0, cantidad * factorSeleccionado / factorControl);
        },

        formatearCantidad(valor, receta) {
            const numero = Number(valor || 0);
            return new Intl.NumberFormat("es-PE", {
                minimumFractionDigits: 0,
                maximumFractionDigits: this.esUnidadDiscreta(receta) ? 0 : 3,
            }).format(Number.isFinite(numero) ? numero : 0);
        },

        normalizarCantidadReceta(receta) {
            let numero = Number(receta.cantidad_por_porcion);
            if (!Number.isFinite(numero)) numero = 1;
            if (this.esUnidadDiscreta(receta)) {
                const factor = Number(this.unidadReceta(receta)?.factor_conversion || 1);
                receta.cantidad_por_porcion = String(
                    Math.max(1 / factor, Math.round(numero * factor) / factor)
                );
            } else {
                receta.cantidad_por_porcion = Math.max(0.0001, numero)
                    .toFixed(4)
                    .replace(/\.?0+$/, "");
            }
            delete this.erroresPlato.receta;
        },

        pasoCantidadReceta(receta) {
            if (!this.esUnidadDiscreta(receta)) return 0.000001;
            return 1 / Number(this.unidadReceta(receta)?.factor_conversion || 1);
        },

        decimal2(valor, minimo = 0, maximo = null) {
            let numero = Number(valor);
            if (!Number.isFinite(numero)) numero = minimo;
            numero = Math.max(minimo, numero);
            if (maximo !== null) numero = Math.min(maximo, numero);
            return numero.toFixed(2);
        },

        normalizarDecimalReceta(receta, campo) {
            receta[campo] = campo === "merma_porcentaje"
                ? this.decimal2(receta[campo], 0, 100)
                : this.decimal2(receta[campo], 0.01);
            delete this.erroresPlato.receta;
        },

        extraerError(data, fallback) {
            if (!data || typeof data !== "object") return fallback;
            const valor = data.detail || data.error || Object.values(data)[0];
            if (Array.isArray(valor)) return valor.join(" ");
            if (valor && typeof valor === "object") return this.extraerError(valor, fallback);
            return valor || fallback;
        },

        getCsrfToken() {
            return (
                document.cookie
                    .split(";")
                    .find((c) => c.trim().startsWith("csrftoken="))
                    ?.split("=")[1] || ""
            );
        },

        // --- Categorías ---
        async fetchCategorias() {
            const res = await fetch("/api/menu/categorias/");
            if (res.ok) this.categorias = await res.json();
        },

        abrirModalCategoria() {
            let siguienteOrden = 1;
            if (this.categorias.length > 0) {
                siguienteOrden = Math.max(...this.categorias.map((c) => c.orden || 0)) + 1;
            }

            this.categoriaForm = {
                id: null,
                nombre: "",
                icono: "restaurant",
                orden: siguienteOrden,
                activo: true,
            };
            this.modalCategoriaInst.show();
        },

        editarCategoria(cat) {
            this.categoriaForm = { ...cat };
            this.modalCategoriaInst.show();
        },

        async guardarCategoria() {
            if (!this.categoriaForm.nombre) return this.mostrarError("El nombre es obligatorio");

            const method = this.categoriaForm.id ? "PUT" : "POST";
            const url = this.categoriaForm.id ? `/api/menu/categorias/${this.categoriaForm.id}/` : "/api/menu/categorias/";

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this.getCsrfToken(),
                    },
                    body: JSON.stringify(this.categoriaForm),
                });

                if (res.ok) {
                    this.modalCategoriaInst.hide();
                    this.fetchCategorias();
                } else {
                    this.mostrarError("Error al guardar categoría");
                }
            } catch (e) {
                console.error(e);
            }
        },

        abrirConfirmarEliminarCategoria(cat) {
            this.categoriaEliminarId = cat.id;
            this.categoriaEliminarNombre = cat.nombre;
            this.categoriaEliminarMensaje = "Si tiene platos asociados, no se podrá eliminar.";
            this.modalEliminarCategoriaInst.show();
        },

        async confirmarEliminarCategoria() {
            if (!this.categoriaEliminarId) return;

            try {
                const res = await fetch(`/api/menu/categorias/${this.categoriaEliminarId}/`, {
                    method: "DELETE",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                });

                if (res.ok) {
                    this.modalEliminarCategoriaInst.hide();
                    this.fetchCategorias();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.categoriaEliminarMensaje = data.detail || data.error || "No se puede eliminar. Verifique que no tenga platos asociados.";
                }
            } catch (e) {
                console.error(e);
                this.categoriaEliminarMensaje = "Error de conexión. Revisa la consola del servidor.";
            }
        },

        // --- Platos ---
        async fetchPlatos() {
            const res = await fetch("/api/menu/platos/");
            if (res.ok) {
                this.platos = await res.json();
                this.platosPaginacion.paginaActual = 1;
            }
        },

        async fetchInsumosDisponibles() {
            try {
                // page_size=500 para traer todos sin paginación; extraer .results del wrapper
                const res = await fetch("/api/inventario/insumos/?activo=true&page_size=500", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                if (res.ok) {
                    const data = await res.json();
                    // La API devuelve {count, results:[...]} — extraemos solo el array
                    this.insumosDisponibles = Array.isArray(data) ? data : (data.results || []);
                } else {
                    console.error("Error cargando insumos:", res.status);
                }
            } catch (e) {
                console.error("Error fetching insumos:", e);
            }
        },

        async fetchInsumoCriticos() {
            try {
                const res = await fetch("/api/menu/platos/insumos_criticos/", {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                if (res.ok) {
                    const data = await res.json();
                    this.insumosCriticos = data.insumos || [];
                }
            } catch (e) {
                console.error("Error fetching insumos críticos:", e);
            }
        },

        async toggleDisponible(plato) {
            // Todo cambio de plato debe quedar motivado y auditado. El acceso
            // rapido abre el mismo editor con la disponibilidad ya invertida.
            await this.editarPlato(plato, { disponible: !plato.disponible });
        },

        abrirConfirmarEliminarPlato(plato) {
            this.platoEliminarId = plato.id;
            this.platoEliminarNombre = plato.nombre;
            this.platoEliminarMotivo = "";
            this.platoEliminarError = "";
            this.modalEliminarPlatoInst.show();
        },

        async confirmarEliminarPlato() {
            if (!this.platoEliminarId) return;

            if (this.eliminandoPlato) return;
            const motivo = (this.platoEliminarMotivo || "").trim();
            if (!motivo) {
                this.platoEliminarError = "Escribe el motivo para retirar el plato del menú.";
                return;
            }

            this.eliminandoPlato = true;
            try {
                const res = await fetch(`/api/menu/platos/${this.platoEliminarId}/`, {
                    method: "DELETE",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this.getCsrfToken(),
                    },
                    body: JSON.stringify({ motivo: motivo.trim() }),
                });

                if (res.ok) {
                    this.modalEliminarPlatoInst.hide();
                    await this.fetchPlatos();
                    this.mostrarExito(`El plato ${this.platoEliminarNombre} fue retirado del menú.`);
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.platoEliminarError = this.extraerError(data, "No se pudo retirar este plato.");
                }
            } catch (e) {
                console.error(e);
                this.platoEliminarError = "No se pudo conectar con el servidor. Inténtalo nuevamente.";
            } finally {
                this.eliminandoPlato = false;
            }
        },

        abrirModalPlato() {
            this.platoOriginal = null;
            this.mensajeAviso = "";
            this.platoForm = {
                id: null,
                categoria: this.filtroCategoriaPlatos || "",
                nombre: "",
                descripcion: "",
                precio_actual: 0.0,
                tiempo_preparacion_min: 15,
                disponible: true,
                activo: true,
                nueva_imagen: null,
                recetas: [],
                motivo: "",
            };
            this.newInsumoId = "";
            this.busquedaInsumo = "";
            this.erroresPlato = {};
            this.imagenPreview = "";
            const fileInput = document.getElementById("imagen_plato_input");
            if (fileInput) fileInput.value = "";
            this.modalPlatoInst.show();
        },

        async editarPlato(plato, cambiosIniciales = {}) {
            if (this.cargandoPlatoId) return false;
            this.cargandoPlatoId = plato.id;
            try {
                const res = await fetch(`/api/menu/platos/${plato.id}/`, {
                    credentials: "same-origin",
                    headers: { Accept: "application/json" },
                });
                if (!res.ok) {
                    const data = await res.json().catch(() => ({}));
                    throw new Error(this.extraerError(data, "No se pudo cargar el plato."));
                }
                const detalle = await res.json();
                const recetasMapeadas = (detalle.receta || []).map((r) => ({
                    id: r.id,
                    insumo_id: r.insumo_id,
                    insumo_nombre: r.insumo_nombre,
                    insumo_unidad: r.unidad_abreviatura || r.insumo_unidad || "",
                    unidad_control: r.unidad_control || "",
                    unidad_control_factor: r.unidad_control_factor || 1,
                    unidad_medida_id: r.unidad_medida_id,
                    unidades_compatibles: r.unidades_compatibles || [],
                    insumo_stock: r.insumo_stock,
                    insumo_es_discreto: Boolean(r.insumo_es_discreto),
                    cantidad_por_porcion: Boolean(r.insumo_es_discreto)
                        ? String(Math.round(Number(r.cantidad_por_porcion)))
                        : String(Number(r.cantidad_por_porcion)),
                    merma_porcentaje: this.decimal2(r.merma_porcentaje, 0, 100),
                    activo: r.activo,
                }));
                const formularioBase = {
                    ...detalle,
                    nueva_imagen: null,
                    recetas: recetasMapeadas,
                    motivo: "",
                };
                this.platoOriginal = JSON.parse(JSON.stringify(formularioBase));
                this.platoForm = { ...formularioBase, ...cambiosIniciales };
                this.mensajeAviso = "";
                this.newInsumoId = "";
                this.busquedaInsumo = "";
                this.erroresPlato = {};
                this.imagenPreview = detalle.imagen_url || "";
                const fileInput = document.getElementById("imagen_plato_input");
                if (fileInput) fileInput.value = "";
                this.modalPlatoInst.show();
                return true;
            } catch (e) {
                console.error(e);
                this.mostrarError(e.message || "No se pudo cargar el plato para editarlo.");
                return false;
            } finally {
                this.cargandoPlatoId = null;
            }
        },

        agregarInsumo() {
            if (!this.newInsumoId) return;

            const insumo = this.insumosDisponibles.find((i) => i.id == this.newInsumoId);
            if (!insumo) return;

            if (!Array.isArray(this.platoForm.recetas)) {
                this.platoForm.recetas = [];
            }

            if (this.platoForm.recetas.some((r) => r.insumo_id == this.newInsumoId)) {
                this.mostrarError("Este insumo ya está agregado");
                return;
            }

            this.platoForm.recetas = [
                ...this.platoForm.recetas,
                {
                    id: null,
                    insumo_id: insumo.id,
                    insumo_nombre: insumo.nombre,
                    insumo_unidad: insumo.unidad_abreviatura || insumo.unidad_nombre || "",
                    unidad_control: insumo.unidad_abreviatura || "",
                    unidad_control_factor: insumo.unidad_factor_conversion || 1,
                    unidad_medida_id: insumo.unidad_medida,
                    unidades_compatibles: insumo.unidades_compatibles || [],
                    insumo_stock: insumo.stock_real,
                    insumo_es_discreto: Boolean(insumo.unidad_es_discreta),
                    cantidad_por_porcion: "1",
                    merma_porcentaje: "0.00",
                    activo: true,
                },
            ];

            this.newInsumoId = "";
            delete this.erroresPlato.receta;
        },

        seleccionarImagen(event) {
            const archivo = event.target.files && event.target.files[0];
            this.platoForm.nueva_imagen = archivo || null;
            if (this.imagenPreview && this.imagenPreview.startsWith("blob:")) {
                URL.revokeObjectURL(this.imagenPreview);
            }
            this.imagenPreview = archivo ? URL.createObjectURL(archivo) : (this.platoForm.imagen_url || "");
        },

        eliminarReceta(receta) {
            if (!Array.isArray(this.platoForm.recetas)) return;
            this.platoForm.recetas = this.platoForm.recetas.filter((r) => r.insumo_id !== receta.insumo_id);
            if (this.platoForm.disponible && this.platoForm.recetas.length === 0) {
                this.erroresPlato.receta = "Agrega al menos un insumo para publicar el plato.";
            }
        },

        validarPlato() {
            const errores = {};
            if (!(this.platoForm.nombre || "").trim()) errores.nombre = "Escribe el nombre del plato.";
            if (!this.platoForm.categoria) errores.categoria = "Selecciona una categoría.";
            if (!(Number(this.platoForm.precio_actual) > 0)) errores.precio_actual = "Ingresa un precio mayor a cero.";
            if (Number(this.platoForm.tiempo_preparacion_min) < 0) errores.tiempo_preparacion_min = "El tiempo no puede ser negativo.";

            const recetas = this.platoForm.recetas || [];
            if (this.platoForm.disponible && recetas.length === 0) {
                errores.receta = "Agrega al menos un insumo para publicar el plato.";
            } else if (recetas.some((r) => !(Number(r.cantidad_por_porcion) > 0))) {
                errores.receta = "Todas las cantidades por porción deben ser mayores a cero.";
            } else if (recetas.some((r) => Number(r.merma_porcentaje) < 0 || Number(r.merma_porcentaje) > 100)) {
                errores.receta = "La merma debe estar entre 0% y 100%.";
            }
            if (!errores.receta && recetas.some((r) =>
                this.esUnidadDiscreta(r) && !Number.isInteger(
                    Number(r.cantidad_por_porcion) * Number(this.unidadReceta(r)?.factor_conversion || 1)
                )
            )) {
                errores.receta = "Las cantidades discretas deben equivaler a unidades base enteras.";
            }
            if (this.requiereMotivoPlato && !(this.platoForm.motivo || "").trim()) {
                errores.motivo = "Explica por qué cambiaste el precio, la receta o la disponibilidad.";
            }
            if (errores.motivo) this.mostrarAvisoMotivo();
            this.erroresPlato = errores;
            return Object.keys(errores).length === 0;
        },

        async guardarPlato() {
            if (this.guardandoPlato || !this.validarPlato()) return;

            const method = this.platoForm.id ? "PATCH" : "POST";
            const url = this.platoForm.id ? `/api/menu/platos/${this.platoForm.id}/` : "/api/menu/platos/";

            const formData = new FormData();
            formData.append("nombre", this.platoForm.nombre);
            formData.append("categoria", this.platoForm.categoria);
            formData.append("precio_actual", this.platoForm.precio_actual);
            formData.append("tiempo_preparacion_min", this.platoForm.tiempo_preparacion_min);
            formData.append("descripcion", this.platoForm.descripcion || "");
            formData.append("disponible", this.platoForm.disponible);
            formData.append("activo", this.platoForm.activo);

            if (this.platoForm.nueva_imagen) {
                formData.append("imagen", this.platoForm.nueva_imagen);
            }

            // Un unico JSON conserva tambien la receta vacia y evita estados
            // parciales cuando se agregan o quitan varios insumos.
            formData.append("receta_json", JSON.stringify(this.platoForm.recetas || []));

            if (this.requiereMotivoPlato) {
                formData.append("motivo", this.platoForm.motivo.trim());
            }

            this.guardandoPlato = true;
            try {
                const res = await fetch(url, {
                    method: method,
                    headers: {
                        "X-CSRFToken": this.getCsrfToken(),
                    },
                    body: formData,
                });

                if (res.ok) {
                    this.mensajeAviso = "";
                    this.modalPlatoInst.hide();
                    await Promise.all([this.fetchPlatos(), this.fetchInsumoCriticos()]);
                    this.mostrarExito(this.platoForm.id ? "Plato actualizado correctamente." : "Plato creado correctamente.");
                } else {
                    const error = await res.json().catch(() => ({}));
                    this.erroresPlato.general = this.extraerError(error, "No se pudo guardar el plato. Revisa los datos.");
                }
            } catch (e) {
                console.error(e);
                this.erroresPlato.general = "No se pudo conectar con el servidor. Inténtalo nuevamente.";
            } finally {
                this.guardandoPlato = false;
            }
        },
    };
}
