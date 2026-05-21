const fs = require('fs');
const html = fs.readFileSync('templates/admin_panel/inventario.html', 'utf8');
const match = html.match(/function inventarioApp\(\) \{\s*return (\{[\s\S]*?\});\s*\}\s*function/);
if (match) {
    const fnBody = 'return ' + match[1] + ';';
    const obj = new Function(fnBody)();
    console.log("Obj initialized.");
    
    // Mock the UI dependencies
    obj.formInsumo = { id: null, nombre: 'choo', unidad_medida: '1', categoria: 'OTRO', stock_minimo: 12, costo_unitario: 12, stock_inicial: 12 };
    obj.formInsumoErrors = {};
    obj.formInsumoWarnings = {};
    obj.pf = v => parseFloat(v) || 0;
    
    try {
        console.log("Calling validarFormInsumo()...");
        const result = obj.validarFormInsumo();
        console.log("Result:", result);
        console.log("Errors:", obj.formInsumoErrors);
        console.log("Preview Valor:", obj.previewValor);
    } catch(e) {
        console.error("Error running validar:", e);
    }
} else {
    console.log("Regex failed to match function.");
}
