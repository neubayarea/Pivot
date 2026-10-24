// Monthly cost budget on the resource group; emails at 80% and 100% of actual spend.
param name string
param amount int
@description('First day of a month, yyyy-MM-dd.')
param startDate string
param contactEmails array

resource budget 'Microsoft.Consumption/budgets@2021-10-01' = {
  name: name
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: { startDate: startDate }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactEmails: contactEmails
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: contactEmails
      }
    }
  }
}
