<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <!-- Budget slider -->
      <div class="card budget-card">
        <div class="budget-head">
          <div>
            <div class="budget-label">{{ t('restocking.budget') }}</div>
            <div class="budget-help">{{ t('restocking.budgetHelp') }}</div>
          </div>
          <div class="budget-value">{{ formatCurrency(budget) }}</div>
        </div>
        <input
          v-model.number="budget"
          type="range"
          class="budget-slider"
          min="0"
          :max="budgetMax"
          :step="BUDGET_STEP"
          :aria-label="t('restocking.budget')"
        />
        <div class="budget-scale">
          <span>{{ formatCurrency(0) }}</span>
          <span>{{ formatCurrency(budgetMax) }}</span>
        </div>
      </div>

      <!-- Summary tiles -->
      <div class="stats-grid">
        <div class="stat-card success">
          <div class="stat-label">{{ t('restocking.allocated') }}</div>
          <div class="stat-value">{{ formatCurrency(summary.allocated) }}</div>
        </div>
        <div class="stat-card info">
          <div class="stat-label">{{ t('restocking.remaining') }}</div>
          <div class="stat-value">{{ formatCurrency(summary.remaining) }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('restocking.itemsRecommended') }}</div>
          <div class="stat-value">{{ summary.recommended_item_count }}</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-label">{{ t('restocking.totalIfAll') }}</div>
          <div class="stat-value">{{ formatCurrency(summary.total_candidate_cost) }}</div>
        </div>
      </div>

      <!-- Recommendations -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <span class="selected-count">
            {{ t('restocking.selectedCount', { count: selectedItems.length, total: recommendations.length }) }}
          </span>
        </div>

        <div v-if="recommendations.length === 0" class="empty-state">
          {{ t('restocking.nothingToRestock') }}
        </div>

        <template v-else>
          <div v-if="summary.recommended_item_count === 0" class="notice">
            {{ t('restocking.noRecommendations') }}
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th class="col-include">{{ t('restocking.table.include') }}</th>
                  <th>{{ t('restocking.table.item') }}</th>
                  <th>{{ t('restocking.table.category') }}</th>
                  <th>{{ t('restocking.table.warehouse') }}</th>
                  <th class="text-right">{{ t('restocking.table.onHand') }}</th>
                  <th class="text-right">{{ t('restocking.table.reorderPoint') }}</th>
                  <th class="text-right">{{ t('restocking.table.demand') }}</th>
                  <th class="text-right">{{ t('restocking.table.forecast') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th class="text-right">{{ t('restocking.table.quantity') }}</th>
                  <th class="text-right">{{ t('restocking.table.unitCost') }}</th>
                  <th class="text-right">{{ t('restocking.table.lineTotal') }}</th>
                  <th>{{ t('restocking.table.leadTime') }}</th>
                  <th>{{ t('restocking.table.priority') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in recommendations"
                  :key="item.sku"
                  :class="{ 'row-over-budget': !item.within_budget }"
                >
                  <td class="col-include">
                    <input
                      type="checkbox"
                      class="row-check"
                      :checked="isSelected(item.sku)"
                      :aria-label="item.name"
                      @change="toggleSelection(item.sku)"
                    />
                  </td>
                  <td>
                    <div class="item-name">{{ translateProductName(item.name) }}</div>
                    <div class="item-sku">{{ item.sku }}</div>
                    <div class="row-flags">
                      <span v-if="item.below_reorder_point" class="flag flag-danger">
                        {{ t('restocking.belowReorderPoint') }}
                      </span>
                      <span :class="['flag', item.within_budget ? 'flag-ok' : 'flag-muted']">
                        {{ item.within_budget ? t('restocking.withinBudget') : t('restocking.overBudget') }}
                      </span>
                    </div>
                  </td>
                  <td>{{ translateCategory(item.category) }}</td>
                  <td>{{ translateWarehouse(item.warehouse) }}</td>
                  <td class="text-right"><strong>{{ item.quantity_on_hand.toLocaleString() }}</strong></td>
                  <td class="text-right">{{ item.reorder_point.toLocaleString() }}</td>
                  <td class="text-right">{{ item.current_demand.toLocaleString() }}</td>
                  <td class="text-right">{{ item.forecasted_demand.toLocaleString() }}</td>
                  <td>
                    <span :class="['badge', item.trend]">{{ t(`trends.${item.trend}`) }}</span>
                  </td>
                  <td class="text-right"><strong>{{ item.recommended_quantity.toLocaleString() }}</strong></td>
                  <td class="text-right">{{ formatUnitCost(item.unit_cost) }}</td>
                  <td class="text-right"><strong>{{ formatCurrency(item.line_total) }}</strong></td>
                  <td>{{ t('orders.leadTimeDays', { days: item.lead_time_days }) }}</td>
                  <td>
                    <span :class="['badge', item.priority]">{{ t(`priority.${item.priority}`) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Selection total + submit -->
          <div class="order-bar">
            <div class="order-totals">
              <div class="order-total-line">
                <span class="order-total-label">{{ t('restocking.allocated') }}</span>
                <span :class="['order-total-value', { 'over': selectionExceedsBudget }]">
                  {{ formatCurrency(selectedTotal) }} / {{ formatCurrency(budget) }}
                </span>
              </div>
              <div class="order-total-meta">
                {{ t('restocking.selectedCount', { count: selectedItems.length, total: recommendations.length }) }}
              </div>
              <div v-if="selectionExceedsBudget" class="warning-inline">
                {{ t('restocking.overBudget') }} &mdash; {{ formatCurrency(selectedTotal - budget) }}
              </div>
            </div>
            <button
              class="place-order-btn"
              :disabled="!canPlaceOrder"
              @click="placeOrder"
            >
              {{ submitting ? t('restocking.placing') : t('restocking.placeOrder') }}
            </button>
          </div>

          <div v-if="successMessage" class="alert alert-success">{{ successMessage }}</div>
          <div v-if="submitError" class="alert alert-error">{{ submitError }}</div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'
import { formatCurrency as formatCurrencyUtil, formatCurrencyWithDecimals } from '../utils/currency'

// Slider granularity, and the rounding applied to the max so the track ends on a clean number
const BUDGET_STEP = 500
const BUDGET_MAX_ROUNDING = 5000
// Slider drags fire continuously; wait for a short pause before hitting the API
const REFETCH_DEBOUNCE_MS = 175

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency, currentLocale, translateProductName, translateWarehouse } = useI18n()

    // Raw API state
    const loading = ref(true)
    const error = ref(null)
    const summary = ref({
      budget: 0,
      allocated: 0,
      remaining: 0,
      recommended_item_count: 0,
      total_candidate_cost: 0
    })
    const recommendations = ref([])

    // Budget slider state
    const budget = ref(0)
    const budgetMax = ref(BUDGET_MAX_ROUNDING)

    // Selection state: SKUs the user wants included in the order
    const selectedSkus = ref([])

    // Submit state
    const submitting = ref(false)
    const successMessage = ref('')
    const submitError = ref('')

    const selectedItems = computed(() =>
      recommendations.value.filter(item => selectedSkus.value.includes(item.sku))
    )

    const selectedTotal = computed(() =>
      selectedItems.value.reduce((sum, item) => sum + item.line_total, 0)
    )

    // Float arithmetic on line totals can land a cent over an exactly-matching budget,
    // so only treat a meaningful overage as exceeding it
    const selectionExceedsBudget = computed(() => selectedTotal.value - budget.value > 0.01)

    const canPlaceOrder = computed(() =>
      selectedItems.value.length > 0 && !selectionExceedsBudget.value && !submitting.value
    )

    const isSelected = (sku) => selectedSkus.value.includes(sku)

    const toggleSelection = (sku) => {
      if (isSelected(sku)) {
        selectedSkus.value = selectedSkus.value.filter(s => s !== sku)
      } else {
        selectedSkus.value = [...selectedSkus.value, sku]
      }
    }

    const applyResponse = (data) => {
      summary.value = {
        budget: data.budget,
        allocated: data.allocated,
        remaining: data.remaining,
        recommended_item_count: data.recommended_item_count,
        total_candidate_cost: data.total_candidate_cost
      }
      recommendations.value = data.recommendations || []
      // A new budget means a new affordable set - the previous manual selection no longer
      // reflects what fits, so snap back to the server's within-budget recommendation
      selectedSkus.value = recommendations.value
        .filter(item => item.within_budget)
        .map(item => item.sku)
    }

    const fetchRecommendations = async () => {
      try {
        const data = await api.getRestockRecommendations(budget.value)
        applyResponse(data)
      } catch (err) {
        error.value = 'Failed to load restock recommendations: ' + err.message
      }
    }

    let refetchTimer = null

    // Keep the previously rendered rows on screen while the request is in flight -
    // blanking the table mid-drag makes the slider feel broken
    watch(budget, () => {
      successMessage.value = ''
      submitError.value = ''
      if (refetchTimer) clearTimeout(refetchTimer)
      refetchTimer = setTimeout(fetchRecommendations, REFETCH_DEBOUNCE_MS)
    })

    const loadInitial = async () => {
      try {
        loading.value = true
        error.value = null

        // A budget of 0 costs nothing to allocate but still reports total_candidate_cost,
        // which is what sizes the slider track
        const probe = await api.getRestockRecommendations(0)
        const ceiling = Math.ceil((probe.total_candidate_cost || 0) / BUDGET_MAX_ROUNDING) * BUDGET_MAX_ROUNDING
        budgetMax.value = Math.max(ceiling, BUDGET_MAX_ROUNDING)

        // Start around half the ceiling so the view opens with a meaningful partial order
        budget.value = Math.round(budgetMax.value / 2 / BUDGET_STEP) * BUDGET_STEP

        // Assigning the budget schedules a debounced refetch; drop it and load once here
        await nextTick()
        if (refetchTimer) clearTimeout(refetchTimer)
        await fetchRecommendations()
      } catch (err) {
        error.value = 'Failed to load restock recommendations: ' + err.message
      } finally {
        loading.value = false
      }
    }

    const placeOrder = async () => {
      if (!canPlaceOrder.value) return

      submitting.value = true
      successMessage.value = ''
      submitError.value = ''
      try {
        const result = await api.submitRestockOrder({
          budget: budget.value,
          items: selectedItems.value.map(item => ({
            sku: item.sku,
            quantity: item.recommended_quantity
          }))
        })
        successMessage.value = t('restocking.orderPlaced', {
          orderNumber: result.order_number,
          date: formatDate(result.expected_delivery),
          days: result.lead_time_days
        })
        // Stock levels moved, so pull a fresh recommendation set for the same budget
        await fetchRecommendations()
      } catch (err) {
        submitError.value = t('restocking.orderFailed')
        console.error('Restock order submit failed:', err)
      } finally {
        submitting.value = false
      }
    }

    const formatCurrency = (value) => formatCurrencyUtil(value || 0, currentCurrency.value)

    // Unit costs are small enough that rounding to whole dollars hides real differences
    const formatUnitCost = (value) => formatCurrencyWithDecimals(value || 0, currentCurrency.value, 2)

    const formatDate = (dateString) => {
      if (!dateString) return ''
      // Parse the YYYY-MM-DD parts explicitly - Date() reads the string as UTC and can
      // shift the delivery date back a day in western timezones
      const parts = String(dateString).split('-').map(Number)
      if (parts.length !== 3 || parts.some(isNaN)) return dateString
      const date = new Date(parts[0], parts[1] - 1, parts[2])
      if (isNaN(date.getTime())) return dateString
      return date.toLocaleDateString(currentLocale.value === 'ja' ? 'ja-JP' : 'en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    }

    const translateCategory = (category) => {
      const categoryMap = {
        'Circuit Boards': t('categories.circuitBoards'),
        'Sensors': t('categories.sensors'),
        'Actuators': t('categories.actuators'),
        'Controllers': t('categories.controllers'),
        'Power Supplies': t('categories.powerSupplies')
      }
      return categoryMap[category] || category
    }

    onMounted(loadInitial)

    onUnmounted(() => {
      if (refetchTimer) clearTimeout(refetchTimer)
    })

    return {
      t,
      BUDGET_STEP,
      loading,
      error,
      summary,
      recommendations,
      budget,
      budgetMax,
      selectedItems,
      selectedTotal,
      selectionExceedsBudget,
      canPlaceOrder,
      submitting,
      successMessage,
      submitError,
      isSelected,
      toggleSelection,
      placeOrder,
      formatCurrency,
      formatUnitCost,
      translateCategory,
      translateProductName,
      translateWarehouse
    }
  }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin-bottom: 0.25rem;
}

.page-header p {
  color: #64748b;
  font-size: 0.875rem;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  color: #64748b;
}

.error {
  color: #ef4444;
}

.budget-card {
  padding: 1.5rem;
}

.budget-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  margin-bottom: 1rem;
}

.budget-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.budget-help {
  margin-top: 0.25rem;
  font-size: 0.813rem;
  color: #94a3b8;
}

.budget-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  white-space: nowrap;
}

.budget-slider {
  width: 100%;
  height: 6px;
  appearance: none;
  -webkit-appearance: none;
  border-radius: 3px;
  background: #e2e8f0;
  cursor: pointer;
}

.budget-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid white;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.25);
  cursor: pointer;
}

.budget-slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #2563eb;
  border: 2px solid white;
  cursor: pointer;
}

.budget-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: #94a3b8;
}

.selected-count {
  font-size: 0.813rem;
  color: #64748b;
}

.empty-state,
.notice {
  padding: 1.5rem;
  text-align: center;
  color: #64748b;
  font-size: 0.875rem;
}

.notice {
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
  text-align: left;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
}

.col-include {
  width: 48px;
  text-align: center;
}

.row-check {
  width: 16px;
  height: 16px;
  accent-color: #2563eb;
  cursor: pointer;
}

.item-name {
  font-weight: 600;
  color: #0f172a;
}

.item-sku {
  font-size: 0.75rem;
  color: #64748b;
  font-family: 'Monaco', 'Courier New', monospace;
}

.row-flags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin-top: 0.25rem;
}

.flag {
  font-size: 0.688rem;
  font-weight: 600;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
}

.flag-danger {
  background: #fecaca;
  color: #991b1b;
}

.flag-ok {
  background: #d1fae5;
  color: #065f46;
}

.flag-muted {
  background: #e2e8f0;
  color: #64748b;
}

/* Over-budget rows stay selectable, just visually receded */
.row-over-budget {
  background: #f8fafc;
  opacity: 0.6;
}

.text-right {
  text-align: right;
}

.order-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.order-total-line {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.order-total-label {
  font-size: 0.813rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.order-total-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: #0f172a;
}

.order-total-value.over {
  color: #dc2626;
}

.order-total-meta {
  margin-top: 0.25rem;
  font-size: 0.813rem;
  color: #64748b;
}

.warning-inline {
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #991b1b;
  font-size: 0.813rem;
  font-weight: 600;
}

.place-order-btn {
  padding: 0.688rem 1.75rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.938rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease;
  white-space: nowrap;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.place-order-btn:disabled {
  background: #cbd5e1;
  color: #f8fafc;
  cursor: not-allowed;
}

.alert {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
}

.alert-success {
  background: #d1fae5;
  border: 1px solid #6ee7b7;
  color: #065f46;
}

.alert-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}
</style>
