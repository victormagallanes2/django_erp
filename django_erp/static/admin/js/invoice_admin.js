// django_erp/static/admin/js/invoice_admin.js

console.log("🔴 SCRIPT DE FACTURACIÓN CARGADO");

// ✅ Función para obtener precio y asignarlo
function fetchProductDetails(productId, row) {
    if (!productId || productId === '') return;
    if (!row) return;
    
    console.log("🔴 Solicitando datos para producto:", productId);
    
    fetch('/admin/invoicing/get-product-price/?product_id=' + productId)
        .then(response => response.json())
        .then(data => {
            console.log("   Datos recibidos:", data);
            
            var priceInput = row.querySelector('input[name$="unit_price"]');
            if (!priceInput) {
                priceInput = row.querySelector('input[id*="unit_price"]');
            }
            
            if (priceInput) {
                priceInput.value = data.unit_price;
                priceInput.setAttribute('readonly', 'readonly');
                priceInput.style.backgroundColor = '#f0f0f0';
                priceInput.style.cursor = 'not-allowed';
                console.log("   ✅ Precio asignado (USD):", data.unit_price);
                priceInput.dispatchEvent(new Event('change', { bubbles: true }));
            }
            
            updateLineSubtotal(row);
            recalculateTotals();
        })
        .catch(error => console.error("Error:", error));
}

function updateLineSubtotal(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    if (!priceInput) {
        var priceDisplay = row.querySelector('.field-unit_price');
        if (priceDisplay) {
            var text = priceDisplay.textContent || '';
            var match = text.match(/\$?\s*(\d+\.?\d*)/);
            if (match) {
                var priceValue = parseFloat(match[1]);
                console.log("   Precio extraído del texto:", priceValue);
                updateTotalsFromValues(row, qtyInput, priceValue);
                return;
            }
        }
        console.log("   ❌ No se encontraron inputs de precio");
        return;
    }
    
    if (!qtyInput) {
        console.log("   ❌ No se encontró input de cantidad");
        return;
    }
    
    var qty = parseFloat(qtyInput.value) || 0;
    var price = parseFloat(priceInput.value) || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado:", qty, "x", price, "=", subtotal);
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en .field-subtotal");
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
        console.log("   ✅ Subtotal actualizado en input");
    }
}

function updateTotalsFromValues(row, qtyInput, priceValue) {
    var qty = parseFloat(qtyInput?.value) || 0;
    var price = priceValue || 0;
    var subtotal = qty * price;
    
    console.log("   Subtotal calculado (fallback):", qty, "x", price, "=", subtotal);
    
    var subtotalField = row.querySelector('.field-subtotal');
    if (subtotalField) {
        subtotalField.textContent = subtotal.toFixed(2);
    }
    
    var subtotalInput = row.querySelector('input[name$="subtotal"]');
    if (subtotalInput) {
        subtotalInput.value = subtotal.toFixed(2);
    }
}

// ✅ Función para recalcular todos los totales
function recalculateTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    console.log("📊 Recalculando totales, filas:", rows.length);
    
    rows.forEach(function(row) {
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = 0;
        
        if (priceInput) {
            price = parseFloat(priceInput.value) || 0;
        } else {
            var priceDisplay = row.querySelector('.field-unit_price');
            if (priceDisplay) {
                var text = priceDisplay.textContent || '';
                var match = text.match(/\$?\s*(\d+\.?\d*)/);
                if (match) {
                    price = parseFloat(match[1]) || 0;
                }
            }
        }
        
        var lineTotal = qty * price;
        subtotal += lineTotal;
        console.log("   Línea: qty=", qty, "price=", price, "total=", lineTotal);
    });
    
    var taxRate = 19;
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    console.log("   Subtotal total USD:", subtotal, "Tax USD:", tax, "Total USD:", total);
    
    // ✅ Obtener tasa de cambio
    var rate = 0;
    var rateField = document.getElementById('id_rate_display');
    if (rateField) {
        var rateText = rateField.value || '';
        var rateMatch = rateText.match(/(\d+\.?\d*)/);
        if (rateMatch) {
            rate = parseFloat(rateMatch[1]);
        }
    }
    if (rate === 0 || isNaN(rate)) {
        rate = 40.00;
    }
    
    console.log("   💰 Tasa usada:", rate);
    
    // ✅ Actualizar campos en USD
    var subtotalField = document.getElementById('id_subtotal_display');
    var taxField = document.getElementById('id_tax_display');
    var totalField = document.getElementById('id_total_display');
    
    if (subtotalField) subtotalField.value = subtotal.toFixed(2);
    if (taxField) taxField.value = tax.toFixed(2);
    if (totalField) totalField.value = total.toFixed(2);
    
    // ✅ Actualizar campos en Bs.
    var subtotalBsField = document.getElementById('id_subtotal_bs_display');
    var taxBsField = document.getElementById('id_tax_bs_display');
    var totalBsField = document.getElementById('id_total_bs_display');
    
    if (subtotalBsField) {
        subtotalBsField.value = (subtotal * rate).toFixed(2);
        console.log("   ✅ Subtotal Bs.:", (subtotal * rate).toFixed(2));
    }
    if (taxBsField) {
        taxBsField.value = (tax * rate).toFixed(2);
        console.log("   ✅ IVA Bs.:", (tax * rate).toFixed(2));
    }
    if (totalBsField) {
        totalBsField.value = (total * rate).toFixed(2);
        console.log("   ✅ Total Bs.:", (total * rate).toFixed(2));
    }
}

// ✅ Configurar eventos en una fila
function setupRow(row) {
    console.log("🔴 Configurando fila");
    
    var select = row.querySelector('select[id$="-product"]');
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    var rowRef = row;
    
    if (select) {
        console.log("   Select de producto encontrado");
        var $ = django.jQuery;
        
        $(select).on('select2:select', function(e) {
            var productId = e.params.data.id;
            console.log("🔴 Producto seleccionado (select2):", productId);
            if (productId) {
                this.value = productId;
                fetchProductDetails(productId, rowRef);
            }
        });
        
        select.addEventListener('change', function() {
            var productId = this.value;
            console.log("🔴 Producto seleccionado (change):", productId);
            if (productId) {
                fetchProductDetails(productId, rowRef);
            }
        });
    }
    
    if (qtyInput) {
        console.log("   Cantidad encontrada");
        qtyInput.addEventListener('change', function() {
            console.log("🔴 Cambio en cantidad:", this.value);
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
    
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            console.log("🔴 Cambio en precio:", this.value);
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
        priceInput.addEventListener('keyup', function() {
            updateLineSubtotal(rowRef);
            recalculateTotals();
        });
    }
}

function setupAllRows() {
    console.log("🔴 Configurando todas las filas...");
    var rows = document.querySelectorAll('tr.form-row');
    console.log("   Filas encontradas:", rows.length);
    rows.forEach(function(row, index) {
        if (!row._hasSetup) {
            row._hasSetup = true;
            console.log(`   Configurando fila ${index}`);
            setupRow(row);
        }
    });
    recalculateTotals();
}

document.addEventListener('click', function(e) {
    var addButton = e.target.closest('.add-row a') || e.target.closest('.add-row');
    if (addButton) {
        console.log("🔴 Botón 'Agregar' clickeado");
        setTimeout(function() {
            var rows = document.querySelectorAll('tr.form-row');
            rows.forEach(function(row) {
                if (!row._hasSetup) {
                    row._hasSetup = true;
                    setupRow(row);
                }
            });
            recalculateTotals();
        }, 300);
        setTimeout(function() {
            recalculateTotals();
        }, 600);
    }
});

function initialize() {
    console.log("🔴 INICIALIZANDO...");
    setupAllRows();
    console.log("✅ Inicialización completada");
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

setTimeout(initialize, 500);
setTimeout(initialize, 1000);
setTimeout(initialize, 2000);

console.log("✅ Script de facturación cargado");