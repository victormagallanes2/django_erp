// django_erp/static/admin/js/physicalcount_admin.js

console.log("🔴 SCRIPT DE AJUSTE DE INVENTARIO CARGADO");

function fetchProductStock(productId) {
    if (!productId) return;
    
    console.log("🔴 Obteniendo stock para producto ID:", productId);
    
    fetch('/admin/inventory/get-product-stock/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("📦 Datos recibidos:", data);
            
            // ✅ Buscar el campo available_quantity
            var availableInput = document.getElementById('id_available_quantity');
            
            if (availableInput) {
                availableInput.value = data.stock;
                availableInput.readOnly = true;
                availableInput.style.backgroundColor = '#f0f0f0';
                availableInput.style.cursor = 'not-allowed';
                console.log("✅ Stock ACTUALIZADO:", data.stock);
            } else {
                console.warn("⚠️ No se encontró id_available_quantity");
            }
        })
        .catch(error => console.error("❌ Error:", error));
}

// ✅ Configurar el select
function setupProductSelect() {
    var productSelect = document.getElementById('id_product');
    
    if (!productSelect) {
        console.warn("⚠️ Select no encontrado, reintentando...");
        setTimeout(setupProductSelect, 500);
        return;
    }
    
    console.log("✅ Select de producto ENCONTRADO");
    
    // ✅ Evento change
    productSelect.addEventListener('change', function() {
        var productId = this.value;
        if (productId) fetchProductStock(productId);
    });
    
    // ✅ Evento Select2
    if (typeof django !== 'undefined' && django.jQuery) {
        var $ = django.jQuery;
        $(productSelect).on('select2:select', function(e) {
            var productId = e.params.data.id;
            if (productId) fetchProductStock(productId);
        });
        console.log("✅ Evento Select2 configurado");
    }
    
    // ✅ Cargar stock inicial
    if (productSelect.value) {
        setTimeout(function() {
            fetchProductStock(productSelect.value);
        }, 200);
    }
}

// ✅ Inicializar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupProductSelect);
} else {
    setupProductSelect();
}

setTimeout(setupProductSelect, 1000);