## Exploration: Funcionalidad de unir mesas (máximo 3)

### Current State
El sistema actual está diseñado para que cada `Comanda` pertenezca a una única `Mesa` mediante una relación `ForeignKey`. 
- El mozo selecciona una mesa en la Pantalla 1 (`toma_pedidos.html`).
- Se crea la comanda vinculada a esa mesa.
- La mesa cambia a estado `OCUPADA`.
- Al liberar la mesa, se busca la comanda activa de esa mesa específica y se cierra.

### Affected Areas
- `apps/comandas/models.py`: Se requiere modificar el modelo `Comanda` para soportar múltiples mesas.
- `apps/comandas/views.py`: 
    - `api_crear_comanda`: Debe aceptar una lista de mesas y marcarlas todas como ocupadas.
    - `api_liberar_mesa`: Debe liberar todas las mesas asociadas a la comanda.
- `apps/mesas/views.py`: 
    - `api_estado_actual`: Debe identificar si una mesa es parte de una unión y mostrar la información de la comanda compartida.
- `templates/mesero/toma_pedidos.html`: El selector de mesas debe permitir selección múltiple (checkboxes o multi-click) y validar el límite de 3.

### Approaches
1. **ManyToMany en `Comanda` (Refactor Total)**: Reemplazar `mesa = ForeignKey` por `mesas = ManyToManyField`.
   - Pros: Consistente y escalable.
   - Cons: Rompe consultas existentes (`comanda.mesa`) y requiere migración de datos compleja.
   - Effort: Medium/High

2. **Campo `mesas_adicionales` (Extensión)**: Mantener `mesa` como "Mesa Principal" y agregar un `ManyToManyField` para mesas extras.
   - Pros: No rompe el código existente que asume una mesa principal. Fácil de implementar.
   - Cons: Lógica duplicada para obtener "todas las mesas" de una comanda.
   - Effort: Low

3. **Mesa "Virtual" o "Contenedora"**: Crear una mesa temporal que represente la unión.
   - Pros: No toca el modelo Comanda.
   - Cons: Muy complejo de gestionar en el plano de mesas físico.
   - Effort: High

### Recommendation
Recomiendo la **Opción 2** por seguridad y velocidad de entrega, pero implementando un método property `todas_las_mesas` en el modelo `Comanda` para centralizar la lógica. Es la forma más limpia de extender la funcionalidad sin romper el dashboard administrativo y los reportes que ya funcionan.

### Risks
- **Integridad de Datos**: Asegurar que al liberar una mesa de una unión, se liberen todas.
- **UI/UX**: El mozo podría confundirse si no hay una indicación clara de que las mesas están "pegadas".
- **Capacidad**: El sistema debe sumar las capacidades de las mesas unidas para informar correctamente.

### Ready for Proposal
Yes — Estamos listos para proponer el cambio al modelo y la interfaz.
