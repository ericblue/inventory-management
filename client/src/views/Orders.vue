<template>
  <div class="orders">
    <div class="page-header">
      <h2>{{ t('orders.title') }}</h2>
      <p>{{ t('orders.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="stats-grid">
        <div class="stat-card success">
          <div class="stat-label">{{ t('status.delivered') }}</div>
          <div class="stat-value">{{ getOrdersByStatus('Delivered').length }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('status.shipped') }}</div>
          <div class="stat-value">{{ getOrdersByStatus('Shipped').length }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('status.processing') }}</div>
          <div class="stat-value">{{ getOrdersByStatus('Processing').length }}</div>
        </div>
        <div class="stat-card danger">
          <div class="stat-label">{{ t('status.backordered') }}</div>
          <div class="stat-value">{{ getOrdersByStatus('Backordered').length }}</div>
        </div>
      </div>

      <div class="card submitted-card">
        <div class="card-header submitted-header">
          <h3 class="card-title">{{ t('orders.submittedOrders') }} ({{ submittedOrders.length }})</h3>
          <p class="card-subtitle">{{ t('orders.submittedDescription') }}</p>
        </div>

        <div v-if="submittedLoading" class="submitted-empty">{{ t('common.loading') }}</div>
        <div v-else-if="submittedOrders.length === 0" class="submitted-empty">
          {{ t('orders.noSubmittedOrders') }}
        </div>
        <div v-else class="submitted-list">
          <div v-for="order in submittedOrders" :key="order.order_number" class="submitted-order">
            <button
              type="button"
              class="submitted-row"
              :aria-expanded="isExpanded(order.order_number) ? 'true' : 'false'"
              @click="toggleExpanded(order.order_number)"
            >
              <span class="submitted-toggle" :class="{ open: isExpanded(order.order_number) }">&#9654;</span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.table.orderNumber') }}</span>
                <strong class="submitted-number">{{ order.order_number }}</strong>
              </span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.table.status') }}</span>
                <span class="badge badge-submitted">{{ submittedStatusLabel(order.status) }}</span>
              </span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.placedOn') }}</span>
                <span>{{ formatSubmittedDate(order.order_date) }}</span>
              </span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.table.expectedDelivery') }}</span>
                <span>{{ formatSubmittedDate(order.expected_delivery) }}</span>
              </span>
              <span class="submitted-field lead-time">
                <span class="submitted-label">{{ t('orders.leadTime') }}</span>
                <strong>{{ t('orders.leadTimeDays', { days: order.lead_time_days }) }}</strong>
              </span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.table.totalValue') }}</span>
                <strong>{{ formatCurrency(order.total_value) }}</strong>
              </span>
              <span class="submitted-field">
                <span class="submitted-label">{{ t('orders.table.items') }}</span>
                <span>{{ t('orders.lines', { count: order.items.length }) }}</span>
              </span>
              <span class="submitted-field submitted-warehouses">
                <span class="submitted-label">{{ t('orders.warehousesLabel') }}</span>
                <span>{{ formatWarehouses(order.warehouses) }}</span>
              </span>
            </button>

            <div v-if="isExpanded(order.order_number)" class="submitted-detail">
              <table class="submitted-items-table">
                <thead>
                  <tr>
                    <th>{{ t('orders.table.items') }}</th>
                    <th class="col-sku">{{ t('inventory.table.sku') }}</th>
                    <th>{{ t('orders.table.category') }}</th>
                    <th>{{ t('orders.table.warehouse') }}</th>
                    <th class="numeric">{{ t('orders.quantity') }}</th>
                    <th class="numeric">{{ t('inventory.table.unitPrice') }}</th>
                    <th class="numeric">{{ t('orders.table.totalValue') }}</th>
                    <th class="numeric">{{ t('orders.leadTime') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in order.items" :key="item.sku">
                    <td>{{ translateProductName(item.name) }}</td>
                    <td class="col-sku">{{ item.sku }}</td>
                    <td>{{ item.category }}</td>
                    <td>{{ translateWarehouse(item.warehouse) }}</td>
                    <td class="numeric">{{ item.quantity.toLocaleString() }}</td>
                    <td class="numeric">{{ formatUnitPrice(item.unit_price) }}</td>
                    <td class="numeric">{{ formatCurrency(item.line_total) }}</td>
                    <td class="numeric">{{ t('orders.leadTimeDays', { days: item.lead_time_days }) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('orders.allOrders') }} ({{ orders.length }})</h3>
        </div>
        <div class="table-container">
          <table class="orders-table">
            <thead>
              <tr>
                <th class="col-order-number">{{ t('orders.table.orderNumber') }}</th>
                <th class="col-customer">{{ t('orders.table.customer') }}</th>
                <th class="col-items">{{ t('orders.table.items') }}</th>
                <th class="col-status">{{ t('orders.table.status') }}</th>
                <th class="col-date">{{ t('orders.table.orderDate') }}</th>
                <th class="col-date">{{ t('orders.table.expectedDelivery') }}</th>
                <th class="col-value">{{ t('orders.table.totalValue') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in orders" :key="order.id">
                <td class="col-order-number"><strong>{{ order.order_number }}</strong></td>
                <td class="col-customer">{{ translateCustomerName(order.customer) }}</td>
                <td class="col-items">
                  <details class="items-details">
                    <summary class="items-summary">
                      {{ t('orders.itemsCount', { count: order.items.length }) }}
                    </summary>
                    <div class="items-dropdown">
                      <div v-for="(item, idx) in order.items" :key="idx" class="item-entry">
                        <span class="item-name">{{ translateProductName(item.name) }}</span>
                        <span class="item-meta">{{ t('orders.quantity') }}: {{ item.quantity }} @ {{ currencySymbol }}{{ item.unit_price }}</span>
                      </div>
                    </div>
                  </details>
                </td>
                <td class="col-status">
                  <span :class="['badge', getOrderStatusClass(order.status)]">
                    {{ t(`status.${order.status.toLowerCase()}`) }}
                  </span>
                </td>
                <td class="col-date">{{ formatDate(order.order_date) }}</td>
                <td class="col-date">{{ formatDate(order.expected_delivery) }}</td>
                <td class="col-value"><strong>{{ currencySymbol }}{{ order.total_value.toLocaleString() }}</strong></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, computed } from 'vue'
import { api } from '../api'
import { useFilters } from '../composables/useFilters'
import { useI18n } from '../composables/useI18n'
import { formatCurrency as formatCurrencyUtil, formatCurrencyWithDecimals } from '../utils/currency'

export default {
  name: 'Orders',
  setup() {
    const { t, currentLocale, currentCurrency, translateProductName, translateCustomerName, translateWarehouse } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })
    const loading = ref(true)
    const error = ref(null)
    const orders = ref([])

    // Submitted restock orders are a separate concept from customer orders:
    // different shape, no customer/status/month dimension, so they get their own
    // state and their own loading flag instead of joining `orders`.
    const submittedOrders = ref([])
    const submittedLoading = ref(true)
    const expandedOrders = ref(new Set())

    // Use shared filters
    const {
      selectedPeriod,
      selectedLocation,
      selectedCategory,
      selectedStatus,
      getCurrentFilters
    } = useFilters()

    const loadOrders = async () => {
      try {
        loading.value = true
        const filters = getCurrentFilters()
        const fetchedOrders = await api.getOrders(filters)

        // Sort orders by order_date (earliest first)
        orders.value = fetchedOrders.sort((a, b) => {
          const dateA = new Date(a.order_date)
          const dateB = new Date(b.order_date)
          return dateA - dateB
        })
      } catch (err) {
        error.value = 'Failed to load orders: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const loadSubmittedOrders = async () => {
      try {
        submittedLoading.value = true
        // API already returns newest-first, so no client-side sort is applied.
        submittedOrders.value = await api.getSubmittedOrders()
      } catch (err) {
        // Fail quietly: this section is supplementary and must never take down
        // the customer orders table if the restock endpoint is unavailable.
        console.error('Failed to load submitted restock orders:', err)
        submittedOrders.value = []
      } finally {
        submittedLoading.value = false
      }
    }

    // Watch for filter changes and reload data
    // NOTE: submitted restock orders are intentionally excluded - the global
    // filter bar has no dimension that applies to them.
    watch([selectedPeriod, selectedLocation, selectedCategory, selectedStatus], () => {
      loadOrders()
    })

    const isExpanded = (orderNumber) => expandedOrders.value.has(orderNumber)

    const toggleExpanded = (orderNumber) => {
      if (expandedOrders.value.has(orderNumber)) {
        expandedOrders.value.delete(orderNumber)
      } else {
        expandedOrders.value.add(orderNumber)
      }
    }

    // Restock status comes from the API as data. Prefer a translated status label
    // when one exists; t() returns the key itself when it does not, in which case
    // we fall back to the raw API value rather than leaking a key into the UI.
    const submittedStatusLabel = (status) => {
      const key = `status.${status.toLowerCase()}`
      const translated = t(key)
      return translated === key ? status : translated
    }

    // Restock dates arrive as date-only strings ("2026-09-27"). new Date() would
    // parse those as UTC midnight and render the previous day in western
    // timezones, so build a local date instead - lead time / delivery dates are
    // the point of this section and must not be off by one.
    const formatSubmittedDate = (dateString) => {
      if (!dateString) return '-'
      const parts = String(dateString).split('-').map(Number)
      if (parts.length !== 3 || parts.some(isNaN)) return dateString
      const date = new Date(parts[0], parts[1] - 1, parts[2])
      if (isNaN(date.getTime())) return dateString
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return date.toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
    }

    const formatWarehouses = (warehouses) => {
      if (!warehouses || warehouses.length === 0) return '-'
      return warehouses.map(translateWarehouse).join(', ')
    }

    const formatCurrency = (value) => formatCurrencyUtil(value, currentCurrency.value)

    // Unit prices are small enough that rounding to whole units loses meaning.
    const formatUnitPrice = (value) => formatCurrencyWithDecimals(value, currentCurrency.value, 2)

    const getOrdersByStatus = (status) => {
      return orders.value.filter(order => order.status === status)
    }

    const getOrderStatusClass = (status) => {
      const statusMap = {
        'Delivered': 'success',
        'Shipped': 'info',
        'Processing': 'warning',
        'Backordered': 'danger'
      }
      return statusMap[status] || 'info'
    }

    const formatDate = (dateString) => {
      const { currentLocale } = useI18n()
      const locale = currentLocale.value === 'ja' ? 'ja-JP' : 'en-US'
      return new Date(dateString).toLocaleDateString(locale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    onMounted(() => {
      loadOrders()
      loadSubmittedOrders()
    })

    return {
      t,
      loading,
      error,
      orders,
      getOrdersByStatus,
      getOrderStatusClass,
      formatDate,
      currencySymbol,
      translateProductName,
      translateCustomerName,
      translateWarehouse,
      submittedOrders,
      submittedLoading,
      isExpanded,
      toggleExpanded,
      submittedStatusLabel,
      formatWarehouses,
      formatSubmittedDate,
      formatCurrency,
      formatUnitPrice
    }
  }
}
</script>

<style scoped>
/* Fixed table layout to prevent column shifting */
.orders-table {
  table-layout: fixed;
  width: 100%;
}

/* Column widths */
.col-order-number {
  width: 130px;
}

.col-customer {
  width: 180px;
}

.col-items {
  width: 200px;
}

.col-status {
  width: 130px;
}

.col-date {
  width: 140px;
}

.col-value {
  width: 120px;
}

/* Items details styling */
.items-details {
  position: relative;
}

.items-summary {
  cursor: pointer;
  color: #3b82f6;
  font-weight: 500;
  list-style: none;
  user-select: none;
  display: inline-block;
}

.items-summary::-webkit-details-marker {
  display: none;
}

.items-summary::before {
  content: '▶';
  display: inline-block;
  margin-right: 0.375rem;
  font-size: 0.75rem;
  transition: transform 0.2s;
}

.items-details[open] .items-summary::before {
  transform: rotate(90deg);
}

.items-summary:hover {
  color: #2563eb;
  text-decoration: underline;
}

/* Dropdown container */
.items-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.5rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  padding: 0.75rem;
  z-index: 10;
  min-width: 300px;
  max-width: 400px;
}

.item-entry {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.5rem;
  border-bottom: 1px solid #f1f5f9;
}

.item-entry:last-child {
  border-bottom: none;
}

.item-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #0f172a;
}

.item-meta {
  font-size: 0.813rem;
  color: #64748b;
}

/* Submitted restock orders */
.submitted-header {
  display: block;
}

.card-subtitle {
  margin: 0.25rem 0 0;
  font-size: 0.875rem;
  color: #64748b;
}

.submitted-empty {
  padding: 2rem 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.938rem;
}

.submitted-list {
  display: flex;
  flex-direction: column;
}

.submitted-order {
  border-bottom: 1px solid #e2e8f0;
}

.submitted-order:last-child {
  border-bottom: none;
}

/* Button element (not a row) so the whole summary is keyboard focusable */
.submitted-row {
  display: grid;
  grid-template-columns: 1rem repeat(4, minmax(110px, 1fr)) minmax(110px, 1fr) minmax(100px, 1fr) minmax(80px, 0.7fr) minmax(140px, 1.2fr);
  gap: 1rem;
  align-items: center;
  width: 100%;
  padding: 1rem 1.5rem;
  background: none;
  border: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.submitted-row:hover {
  background: #f8fafc;
}

.submitted-toggle {
  color: #64748b;
  font-size: 0.625rem;
  transition: transform 0.2s;
}

.submitted-toggle.open {
  transform: rotate(90deg);
}

.submitted-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
  font-size: 0.875rem;
  color: #0f172a;
}

.submitted-label {
  font-size: 0.688rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  color: #64748b;
}

/* Lead time is the headline of this section, so it gets extra emphasis */
.submitted-field.lead-time strong {
  font-size: 1rem;
  color: #4338ca;
}

.submitted-number {
  color: #0f172a;
}

.submitted-warehouses {
  overflow-wrap: anywhere;
}

.badge-submitted {
  background: #e0e7ff;
  color: #3730a3;
}

.submitted-detail {
  padding: 0 1.5rem 1.25rem 2.5rem;
  background: #f8fafc;
}

.submitted-items-table {
  width: 100%;
  border-collapse: collapse;
}

.submitted-items-table th,
.submitted-items-table td {
  padding: 0.625rem 0.75rem;
  font-size: 0.875rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
}

.submitted-items-table th {
  font-size: 0.688rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  color: #64748b;
}

.submitted-items-table tbody tr:last-child td {
  border-bottom: none;
}

.submitted-items-table .numeric {
  text-align: right;
}

.submitted-items-table .col-sku {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 0.813rem;
  color: #64748b;
}
</style>
