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
        },
        platoEliminarId: null,
        platoEliminarNombre: "",
        platoEliminarMensaje: "Esta acción no se puede deshacer.",

        newInsumoId: "",

        platosPaginacion: {
            paginaActual: 1,
            porPagina: 5,
            totalPaginas: 1,
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
            try {
                const res = await fetch(`/api/menu/platos/${plato.id}/`, {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": this.getCsrfToken(),
                    },
                    body: JSON.stringify({ disponible: !plato.disponible }),
                });
                if (res.ok) {
                    const updated = await res.json();
                    plato.disponible = updated.disponible;
                } else {
                    console.error("Error al cambiar disponibilidad");
                }
            } catch (e) {
                console.error(e);
            }
        },

        abrirConfirmarEliminarPlato(plato) {
            this.platoEliminarId = plato.id;
            this.platoEliminarNombre = plato.nombre;
            this.platoEliminarMensaje = "Esta acción no se puede deshacer.";
            this.modalEliminarPlatoInst.show();
        },

        async confirmarEliminarPlato() {
            if (!this.platoEliminarId) return;

            try {
                const res = await fetch(`/api/menu/platos/${this.platoEliminarId}/`, {
                    method: "DELETE",
                    headers: { "X-CSRFToken": this.getCsrfToken() },
                });

                if (res.ok) {
                    this.modalEliminarPlatoInst.hide();
                    this.fetchPlatos();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.platoEliminarMensaje = data.detail || data.error || "No se puede eliminar este plato.";
                }
            } catch (e) {
                console.error(e);
                this.platoEliminarMensaje = "Error de conexión. Revisa la consola del servidor.";
            }
        },

        abrirModalPlato() {
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
            };
            this.newInsumoId = "";
            const fileInput = document.getElementById("imagen_plato_input");
            if (fileInput) fileInput.value = "";
            this.modalPlatoInst.show();
        },

        editarPlato(plato) {
            const recetasMapeadas = (plato.receta || []).map((r) => ({
                id: r.id,
                insumo_id: r.insumo_id,
                insumo_nombre: r.insumo_nombre,
                insumo_unidad: r.unidad_abreviatura || r.insumo_unidad || "",
                insumo_stock: r.insumo_stock,
                cantidad_por_porcion: r.cantidad_por_porcion,
                merma_porcentaje: r.merma_porcentaje,
                activo: r.activo,
            }));
            this.platoForm = {
                ...plato,
                nueva_imagen: null,
                recetas: recetasMapeadas,
            };
            this.newInsumoId = "";
            const fileInput = document.getElementById("imagen_plato_input");
            if (fileInput) fileInput.value = "";
            this.modalPlatoInst.show();
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
                    insumo_stock: insumo.stock_real,
                    cantidad_por_porcion: 1,
                    merma_porcentaje: 0,
                    activo: true,
                },
            ];

            this.newInsumoId = "";
        },

        eliminarReceta(receta) {
            if (!Array.isArray(this.platoForm.recetas)) return;
            this.platoForm.recetas = this.platoForm.recetas.filter((r) => r.insumo_id !== receta.insumo_id);
        },

        async guardarPlato() {
            if (!this.platoForm.nombre || !this.platoForm.categoria || !this.platoForm.precio_actual) {
                return this.mostrarError("Nombre, categoría y precio son obligatorios");
            }

            const method = this.platoForm.id ? "PUT" : "POST";
            const url = this.platoForm.id ? `/api/menu/platos/${this.platoForm.id}/` : "/api/menu/platos/";

            const formData = new FormData();
            formData.append("nombre", this.platoForm.nombre);
            formData.append("categoria", this.platoForm.categoria);
            formData.append("precio_actual", this.platoForm.precio_actual);
            formData.append("tiempo_preparacion_min", this.platoForm.tiempo_preparacion_min);
            if (this.platoForm.descripcion) formData.append("descripcion", this.platoForm.descripcion);
            formData.append("disponible", this.platoForm.disponible);
            formData.append("activo", this.platoForm.activo);

            if (this.platoForm.nueva_imagen) {
                formData.append("imagen", this.platoForm.nueva_imagen);
            }

            this.platoForm.recetas.forEach((receta) => {
                formData.append(`receta`, JSON.stringify(receta));
            });

            try {
                const res = await fetch(url, {
                    method: method,
                    headers: {
                        "X-CSRFToken": this.getCsrfToken(),
                    },
                    body: formData,
                });

                if (res.ok) {
                    this.modalPlatoInst.hide();
                    this.fetchPlatos();
                    this.fetchInsumoCriticos();
                } else {
                    const error = await res.json();
                    console.error(error);
                    this.mostrarError("Error al guardar plato. Verifique los datos.");
                }
            } catch (e) {
                console.error(e);
            }
        },
    };
}