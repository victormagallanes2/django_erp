// django_erp/static/admin/js/purchase_invoice_admin.js
console.log("🔴 SCRIPT DE FACTURAS DE COMPRA CARGADO");

function recalculateInvoiceTotals() {
    var subtotal = 0;
    var rows = document.querySelectorAll('tr.form-row');
    
    rows.forEach(function(row) {
        var qtyInput = row.querySelector('input[name$="quantity"]');
        var priceInput = row.querySelector('input[name$="unit_price"]');
        var qty = parseFloat(qtyInput?.value) || 0;
        var price = parseFloat(priceInput?.value) || 0;
        subtotal += qty * price;
    });
    
    var taxRate = 16;
    var tax = subtotal * (taxRate / 100);
    var total = subtotal + tax;
    
    var subtotalField = document.getElementById('id_subtotal');
    var taxField = document.getElementById('id_tax');
    var totalField = document.getElementById('id_total');
    
    if (subtotalField) subtotalField.value = subtotal.toFixed(2);
    if (taxField) taxField.value = tax.toFixed(2);
    if (totalField) totalField.value = total.toFixed(2);
}

// Configurar eventos en líneas
function setupInvoiceLine(row) {
    var qtyInput = row.querySelector('input[name$="quantity"]');
    var priceInput = row.querySelector('input[name$="unit_price"]');
    
    if (qtyInput) {
        qtyInput.addEventListener('change', function() {
            recalculateInvoiceTotals();
        });
        qtyInput.addEventListener('keyup', function() {
            recalculateInvoiceTotals();
        });
    }
    
    if (priceInput) {
        priceInput.addEventListener('change', function() {
            recalculateInvoiceTotals();
        });
        priceInput.addEventListener('keyup', function() {
            recalculateInvoiceTotals();
        });
    }
}

// Inicializar
function initialize() {
    var rows = document.querySelectorAll('tr.form-row');
    rows.forEach(function(row) {
        if (!row._hasInvoiceSetup) {
            row._hasInvoiceSetup = true;
            setupInvoiceLine(row);
        }
    });
    recalculateInvoiceTotals();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

setTimeout(initialize, 500);
setTimeout(initialize, 1000);