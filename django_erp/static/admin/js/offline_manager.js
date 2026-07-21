// static/admin/js/offline_manager.js

// ✅ ✅ ✅ Prevenir duplicados
if (typeof window.OfflineManager === 'undefined') {

class OfflineManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.pendingCount = 0;
        this.db = null;
        this.dbName = 'ERP_Offline_DB';
        this.dbVersion = 1;
        this.syncInterval = null;
        this.isSyncing = false;
        
        this.init();
    }

    // ============================================================
    // INICIALIZACIÓN
    // ============================================================
    
    async init() {
        console.log('📱 Inicializando Offline Manager...');
        
        // ✅ Inicializar IndexedDB
        await this.initDB();
        
        // ✅ Configurar eventos de conexión
        window.addEventListener('online', () => this.handleOnline());
        window.addEventListener('offline', () => this.handleOffline());
        
        // ✅ Verificar conexión cada 30 segundos
        this.syncInterval = setInterval(() => {
            this.checkConnection();
        }, 30000);
        
        // ✅ Actualizar contador de pendientes
        await this.updatePendingCount();
        
        // ✅ Si hay internet, sincronizar al inicio
        if (this.isOnline) {
            setTimeout(() => this.syncPending(), 3000);
        }
        
        // ✅ Actualizar UI
        this.updateUI();
        
        console.log('✅ Offline Manager inicializado');
        console.log(`📶 Estado: ${this.isOnline ? 'Online' : 'Offline'}`);
        console.log(`📄 Pendientes: ${this.pendingCount}`);
    }

    // ============================================================
    // INDEXEDDB
    // ============================================================
    
    async initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // ✅ Tabla de facturas pendientes
                if (!db.objectStoreNames.contains('pending_invoices')) {
                    const store = db.createObjectStore('pending_invoices', { 
                        keyPath: 'uuid' 
                    });
                    store.createIndex('created_at', 'created_at');
                    store.createIndex('sync_status', 'sync_status');
                    store.createIndex('customer_name', 'customer_name');
                    console.log('📦 Tabla pending_invoices creada');
                }
                
                // ✅ Tabla de líneas de factura
                if (!db.objectStoreNames.contains('pending_invoice_lines')) {
                    const store = db.createObjectStore('pending_invoice_lines', { 
                        keyPath: 'uuid' 
                    });
                    store.createIndex('invoice_uuid', 'invoice_uuid');
                    console.log('📦 Tabla pending_invoice_lines creada');
                }
            };
            
            request.onsuccess = (event) => {
                this.db = event.target.result;
                console.log('✅ IndexedDB conectada');
                resolve();
            };
            
            request.onerror = (event) => {
                console.error('❌ Error IndexedDB:', event.target.error);
                reject(event.target.error);
            };
        });
    }

    // ============================================================
    // OPERACIONES CON FACTURAS
    // ============================================================
    
    async saveInvoice(invoiceData) {
        if (!this.db) await this.initDB();
        
        // ✅ Asegurar UUID
        if (!invoiceData.uuid) {
            invoiceData.uuid = this.generateUUID();
        }
        
        // ✅ Agregar metadatos
        invoiceData.sync_status = 'PENDING';
        invoiceData.created_at = new Date().toISOString();
        invoiceData.sync_attempts = 0;
        invoiceData.device_id = this.getDeviceId();
        
        try {
            const tx = this.db.transaction(['pending_invoices', 'pending_invoice_lines'], 'readwrite');
            
            // ✅ Guardar factura
            const invoiceStore = tx.objectStore('pending_invoices');
            invoiceStore.put(invoiceData);
            
            // ✅ Guardar líneas
            const lineStore = tx.objectStore('pending_invoice_lines');
            if (invoiceData.lines && invoiceData.lines.length > 0) {
                for (const line of invoiceData.lines) {
                    if (!line.uuid) line.uuid = this.generateUUID();
                    line.invoice_uuid = invoiceData.uuid;
                    line.sync_status = 'PENDING';
                    lineStore.put(line);
                }
            }
            
            return new Promise((resolve, reject) => {
                tx.oncomplete = () => {
                    console.log(`✅ Factura ${invoiceData.number || invoiceData.uuid} guardada localmente`);
                    this.updatePendingCount();
                    this.showNotification('💾 Factura guardada localmente');
                    resolve({ success: true, uuid: invoiceData.uuid });
                };
                tx.onerror = (event) => {
                    console.error('❌ Error guardando:', event.target.error);
                    reject(event.target.error);
                };
            });
            
        } catch (error) {
            console.error('❌ Error en saveInvoice:', error);
            throw error;
        }
    }

    async getPendingInvoices() {
        if (!this.db) await this.initDB();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(['pending_invoices'], 'readonly');
            const store = tx.objectStore('pending_invoices');
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async getInvoiceLines(invoiceUuid) {
        if (!this.db) await this.initDB();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(['pending_invoice_lines'], 'readonly');
            const store = tx.objectStore('pending_invoice_lines');
            const index = store.index('invoice_uuid');
            const request = index.getAll(invoiceUuid);
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async deleteInvoice(uuid) {
        if (!this.db) await this.initDB();
        
        try {
            // ✅ Eliminar factura
            const tx1 = this.db.transaction(['pending_invoices'], 'readwrite');
            tx1.objectStore('pending_invoices').delete(uuid);
            
            // ✅ Eliminar líneas
            const tx2 = this.db.transaction(['pending_invoice_lines'], 'readwrite');
            const index = tx2.objectStore('pending_invoice_lines').index('invoice_uuid');
            
            return new Promise((resolve) => {
                const request = index.getAll(uuid);
                request.onsuccess = () => {
                    const lines = request.result;
                    const store = tx2.objectStore('pending_invoice_lines');
                    for (const line of lines) {
                        store.delete(line.uuid);
                    }
                    tx2.oncomplete = () => {
                        this.updatePendingCount();
                        resolve();
                    };
                };
            });
            
        } catch (error) {
            console.error('❌ Error eliminando:', error);
            throw error;
        }
    }

    async updateInvoice(invoice) {
        if (!this.db) await this.initDB();
        
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(['pending_invoices'], 'readwrite');
            const store = tx.objectStore('pending_invoices');
            const request = store.put(invoice);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    // ============================================================
    // SINCRONIZACIÓN
    // ============================================================
    
    async syncPending() {
        if (this.isSyncing) {
            console.log('⏳ Ya hay una sincronización en curso');
            return;
        }
        
        if (!this.isOnline) {
            console.log('⚠️ Sin internet, no se puede sincronizar');
            return;
        }
        
        this.isSyncing = true;
        this.showNotification('🔄 Sincronizando facturas pendientes...');
        
        try {
            const invoices = await this.getPendingInvoices();
            const pending = invoices.filter(i => 
                i.sync_status === 'PENDING' || i.sync_status === 'FAILED'
            );
            
            if (pending.length === 0) {
                console.log('✅ No hay facturas pendientes');
                this.showNotification('✅ No hay facturas pendientes');
                this.isSyncing = false;
                return;
            }
            
            console.log(`🔄 Sincronizando ${pending.length} facturas...`);
            
            let synced = 0;
            let failed = 0;
            
            for (const invoice of pending) {
                try {
                    // ✅ Marcar como sincronizando
                    invoice.sync_status = 'SYNCING';
                    await this.updateInvoice(invoice);
                    
                    // ✅ Enviar al servidor
                    const response = await fetch('/admin/invoicing/sync-offline/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': this.getCSRFToken()
                        },
                        body: JSON.stringify(invoice)
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        await this.deleteInvoice(invoice.uuid);
                        synced++;
                        console.log(`✅ Factura ${invoice.number || invoice.uuid} sincronizada`);
                    } else {
                        invoice.sync_status = 'FAILED';
                        invoice.sync_attempts++;
                        invoice.sync_error = result.error || 'Error desconocido';
                        await this.updateInvoice(invoice);
                        failed++;
                        console.error(`❌ Error sincronizando ${invoice.uuid}:`, result.error);
                    }
                    
                } catch (error) {
                    invoice.sync_status = 'FAILED';
                    invoice.sync_attempts++;
                    invoice.sync_error = error.message;
                    await this.updateInvoice(invoice);
                    failed++;
                    console.error(`❌ Error sincronizando ${invoice.uuid}:`, error);
                }
            }
            
            this.updatePendingCount();
            this.showNotification(`✅ ${synced} sincronizadas, ${failed} fallidas`);
            console.log(`✅ Sincronización completada: ${synced} OK, ${failed} ERROR`);
            
        } catch (error) {
            console.error('❌ Error en syncPending:', error);
            this.showNotification('❌ Error en sincronización');
        }
        
        this.isSyncing = false;
    }

    // ============================================================
    // EVENTOS DE CONEXIÓN
    // ============================================================
    
    handleOnline() {
        this.isOnline = true;
        console.log('📶 Conexión restablecida');
        this.updateUI();
        this.showNotification('📶 Conexión restablecida');
        
        // ✅ Sincronizar automáticamente
        setTimeout(() => this.syncPending(), 2000);
    }

    handleOffline() {
        this.isOnline = false;
        console.log('📶 Sin conexión');
        this.updateUI();
        this.showNotification('⚠️ Sin conexión - Las facturas se guardarán localmente', 'warning');
    }

    async checkConnection() {
        try {
            const response = await fetch('/admin/health-check/', { 
                method: 'HEAD',
                cache: 'no-cache'
            });
            
            if (response.ok && !this.isOnline) {
                this.handleOnline();
            } else if (!response.ok && this.isOnline) {
                this.handleOffline();
            }
        } catch (error) {
            if (this.isOnline) {
                this.handleOffline();
            }
        }
    }

    // ============================================================
    // CONTADOR DE PENDIENTES
    // ============================================================
    
    async updatePendingCount() {
        try {
            const invoices = await this.getPendingInvoices();
            this.pendingCount = invoices.filter(i => 
                i.sync_status === 'PENDING' || i.sync_status === 'FAILED'
            ).length;
            this.updateUI();
        } catch (error) {
            console.error('Error actualizando contador:', error);
        }
    }

    // ============================================================
    // INTERFAZ DE USUARIO
    // ============================================================
    
    updateUI() {
        // ✅ Badge de pendientes (en el header)
        const badge = document.getElementById('offline-badge');
        if (badge) {
            if (this.pendingCount > 0) {
                badge.textContent = this.pendingCount;
                badge.style.display = 'inline';
                badge.title = `${this.pendingCount} facturas pendientes`;
            } else {
                badge.style.display = 'none';
            }
        }
        
        // ✅ Indicador de conexión
        const dot = document.getElementById('connection-dot');
        const text = document.getElementById('connection-text');
        if (dot && text) {
            if (this.isOnline) {
                dot.className = 'dot online';
                text.textContent = 'Online';
            } else {
                dot.className = 'dot offline';
                text.textContent = 'Offline';
            }
        }
        
        // ✅ Botón de sincronización
        const syncBtn = document.getElementById('sync-button-header');
        if (syncBtn) {
            if (this.pendingCount > 0 && this.isOnline) {
                syncBtn.classList.add('show');
                syncBtn.textContent = `🔄 Sincronizar (${this.pendingCount})`;
                syncBtn.disabled = false;
            } else if (this.pendingCount > 0 && !this.isOnline) {
                syncBtn.classList.add('show');
                syncBtn.textContent = `⏳ ${this.pendingCount} pendientes`;
                syncBtn.disabled = true;
            } else {
                syncBtn.classList.remove('show');
                syncBtn.disabled = false;
            }
        }
        
        // ✅ Banner offline
        const banner = document.getElementById('offline-banner');
        if (banner) {
            if (!this.isOnline) {
                banner.classList.add('visible');
                banner.innerHTML = `
                    ⚠️ <strong>Sin conexión</strong> - Las facturas se guardarán localmente.
                    <span id="offline-count">${this.pendingCount}</span> facturas pendientes.
                `;
            } else if (this.pendingCount > 0) {
                banner.classList.add('visible');
                banner.innerHTML = `
                    ⚠️ <strong>${this.pendingCount} facturas pendientes</strong> - 
                    <a href="#" onclick="if(window.offlineManager) { window.offlineManager.syncPending(); } return false;" style="color:#155724;font-weight:bold;">
                        Sincronizar ahora
                    </a>
                `;
            } else {
                banner.classList.remove('visible');
                banner.innerHTML = '';
            }
        }
    }

    // ============================================================
    // NOTIFICACIONES
    // ============================================================
    
    showNotification(message, type = 'info') {
        // ✅ Verificar que no haya muchas notificaciones
        const existing = document.querySelectorAll('.offline-toast');
        if (existing.length > 3) {
            existing[0].remove();
        }
        
        const toast = document.createElement('div');
        toast.className = `offline-toast ${type}`;
        toast.textContent = message;
        
        const colors = {
            info: '#28a745',
            warning: '#ffc107',
            error: '#dc3545'
        };
        
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            background: ${colors[type] || colors.info};
            color: ${type === 'warning' ? '#333' : 'white'};
            border-radius: 8px;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease;
            font-weight: bold;
            max-width: 400px;
            font-size: 14px;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.5s';
            setTimeout(() => toast.remove(), 500);
        }, 4000);
    }

    // ============================================================
    // UTILIDADES
    // ============================================================
    
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    getDeviceId() {
        let deviceId = localStorage.getItem('device_id');
        if (!deviceId) {
            deviceId = this.generateUUID();
            localStorage.setItem('device_id', deviceId);
        }
        return deviceId;
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// ✅ ✅ ✅ Solo crear la instancia una vez
if (typeof window.offlineManager === 'undefined') {
    document.addEventListener('DOMContentLoaded', async () => {
        if (!window.offlineManager) {
            window.offlineManager = new OfflineManager();
            console.log('✅ Offline Manager inicializado (única instancia)');
        }
    });
}

} else {
    console.log('⚠️ OfflineManager ya existe, no se vuelve a cargar');
}

// ✅ ✅ ✅ Estilos para notificaciones (solo si no existen)
if (!document.getElementById('offline-manager-styles')) {
    const style = document.createElement('style');
    style.id = 'offline-manager-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateY(100%);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }
        
        #offline-badge {
            background: #dc3545;
            color: white;
            border-radius: 50%;
            padding: 1px 7px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 8px;
            display: none;
            min-width: 20px;
            text-align: center;
            vertical-align: middle;
        }
        
        .connection-indicator {
            display: inline-flex;
            align-items: center;
            margin-right: 15px;
            font-size: 13px;
            color: #6c757d;
            font-weight: normal;
        }
        
        .connection-indicator .dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 6px;
            display: inline-block;
        }
        
        .connection-indicator .dot.online {
            background: #28a745;
        }
        
        .connection-indicator .dot.offline {
            background: #dc3545;
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.3; }
            100% { opacity: 1; }
        }
        
        #sync-button-header {
            background: #2d6a4f;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 4px 12px;
            font-size: 12px;
            cursor: pointer;
            margin-right: 15px;
            display: none;
        }
        
        #sync-button-header:hover {
            background: #1b4332;
        }
        
        #sync-button-header.show {
            display: inline-block;
        }
        
        #sync-button-header:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        #offline-banner {
            background: #fff3cd;
            border-bottom: 2px solid #ffc107;
            padding: 8px 20px;
            display: none;
            text-align: center;
            font-size: 14px;
            color: #856404;
        }
        
        #offline-banner.visible {
            display: block;
        }
        
        #offline-banner a {
            color: #856404;
            text-decoration: underline;
            cursor: pointer;
        }
        
        #offline-banner a:hover {
            color: #533f03;
        }
    `;
    document.head.appendChild(style);
}