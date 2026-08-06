// django_erp/static/admin/js/company_switcher.js

(function() {
    'use strict';
    
    console.log('📢 company_switcher.js cargado');
    console.log('   Alpine disponible:', typeof Alpine !== 'undefined');
    
    if (typeof Alpine === 'undefined') {
        console.error('❌ Alpine NO está disponible');
        return;
    }
    
    // ✅ Registrar el componente
    Alpine.data('companySwitcher', function() {
        return {
            isOpen: false,
            currentCompanyId: null,
            currentCompanyName: '',
            currentCompanyCode: '',
            availableCompanies: [],

            init: function() {
                var self = this;
                
                console.log('🏢 Inicializando companySwitcher...');
                
                try {
                    self.availableCompanies = window.COMPANIES_DATA || [];
                    
                    if (!Array.isArray(self.availableCompanies)) {
                        self.availableCompanies = [];
                    }
                    
                    self.currentCompanyId = window.CURRENT_COMPANY_ID || null;
                    
                    console.log('📋 Compañías:', self.availableCompanies.length);
                    console.log('📌 ID actual:', self.currentCompanyId);
                    
                    if (self.availableCompanies.length > 0) {
                        // Buscar la compañía actual
                        if (self.currentCompanyId) {
                            var current = self.availableCompanies.find(function(c) {
                                return String(c.id) === String(self.currentCompanyId);
                            });
                            if (current) {
                                self.currentCompanyName = current.name;
                                self.currentCompanyCode = current.code;
                            }
                        }
                        
                        // Si no se encontró, usar la primera
                        if (!self.currentCompanyName && self.availableCompanies.length > 0) {
                            self.currentCompanyId = self.availableCompanies[0].id;
                            self.currentCompanyName = self.availableCompanies[0].name;
                            self.currentCompanyCode = self.availableCompanies[0].code;
                        }
                    }
                    
                    console.log('✅ Company Switcher listo:');
                    console.log('   Compañía:', self.currentCompanyCode, '-', self.currentCompanyName);
                    console.log('   Total:', self.availableCompanies.length);
                    
                } catch (e) {
                    console.error('❌ Error:', e);
                    self.availableCompanies = [];
                }
            }
        };
    });
    
    console.log('✅ Componente companySwitcher registrado en Alpine');
    
})();