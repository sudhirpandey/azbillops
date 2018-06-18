import adal
import requests
import os
import sys
import json
import datetime
import time
import calendar
import pytz
import urllib
import argparse
import dateutil.parser
from pprint import pprint

def round_time(date, hour):
  return date.replace(microsecond=0,second=0,minute=0) - datetime.timedelta(hours=hour)

def get_token():
  authentication_endpoint = 'https://login.microsoftonline.com/'
  resource = 'https://management.azure.com/'
  #resource  = 'https://management.core.windows.net/'
  if os.environ.get('TENANTID') is not None:
     tenant_id = os.environ.get('TENANTID')
  else:
     print("please set TENANTID as environment variable")
     sys.exit(1)

  if os.environ.get('APPID') is not None:
     application_id = os.environ.get('APPID')
  else:
     print("please set APPID as environment variable")
     sys.exit(1)

  if os.environ.get('SECRET') is not None:
     application_secret = os.environ.get('SECRET')
  else:
     print("please set SECRET as environment variable")
     sys.exit(1)
  
  # get an Azure access token using the adal library
  context = adal.AuthenticationContext(authentication_endpoint + tenant_id)
  token_response = context.acquire_token_with_client_credentials(resource, application_id, application_secret)
  
  access_token = token_response.get('accessToken')
  #printubscription['subscriptionId'])access_token)
  return access_token


def get_api_resource( url, params={'api-version': '2018-02-01'} ):
  access_token = get_token()
  headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
  r = requests.get(url, headers=headers, params=params)
  return r



def get_subscriptions():
  params = {'api-version': '2018-02-01'}
  url = 'https://management.azure.com/' + 'subscriptions'
  subscriptions=get_api_resource(url, params)
  #print(json.dumps(subscriptions.json(), indent=4, separators=(',', ': ')))
  return subscriptions



def get_billing_periods(subscription_id):
 url = 'https://management.azure.com/subscriptions/' + subscription_id + '/providers/Microsoft.Billing/billingPeriods'
 params = {'api-version': '2017-04-24-preview'} 
 billperiods = get_api_resource(url, params=params)
 #print(json.dumps(billperiods.json(), indent=4, separators=(',', ': ')))
 return billperiods


def get_usage_for_billing_period(subscription_id,startdate,enddate,resolution='Hourly'):
   startdate = datetime.datetime.strptime(startdate, "%Y-%m-%d")
   enddate = datetime.datetime.strptime(enddate, "%Y-%m-%d")
   currentdate = datetime.datetime.utcnow() 

   startdate_utc=pytz.utc.localize(startdate)
   enddate_utc=pytz.utc.localize(enddate)
   currentdate_utc = pytz.utc.localize(currentdate)

   calculate_cost_for_today = False
   hourlyUsageForToday = None
  
   if currentdate_utc < enddate_utc:
     #the enddate_utc time needs to be rounded to lower hour or 2 mark as api expects it to be hourly
     #print ("Now:"+ currentdate_utc.isoformat())
     if resolution == 'Hourly':
        enddate_utc = round_time(currentdate_utc,2)

     if resolution == 'Daily':
        enddate_utc = round_time(currentdate_utc,currentdate_utc.hour)
        calculate_cost_for_today = True

   params = {'api-version': '2015-06-01-preview' }
   request = { 'reportedStartTime' :  startdate_utc.isoformat() , 'reportedEndTime': enddate_utc.isoformat() }
   
   print ("Calculating "+ resolution +" From:"+startdate_utc.isoformat()+ "  To:"+ enddate_utc.isoformat())
   url = 'https://management.azure.com/subscriptions/'+ subscription_id +'/providers/Microsoft.Commerce/UsageAggregates?' + urllib.urlencode(request) +'"&aggregationGranularity='+ resolution +'&showDetails=true"'
   #print (url)
   Usage = get_api_resource(url, params)
   #print(json.dumps(Usage.json(), indent=4, separators=(',', ': ')))

   if calculate_cost_for_today == True:
      starttime=enddate_utc.isoformat()
      endtime=round_time(currentdate_utc,2).isoformat()
      request = { 'reportedStartTime' :  starttime , 'reportedEndTime': endtime }
      print ("Calculating hourly From:"+starttime+ "  To:"+ endtime)
      url = 'https://management.azure.com/subscriptions/'+ subscription_id +'/providers/Microsoft.Commerce/UsageAggregates?' + urllib.urlencode(request) +'"&aggregationGranularity=Hourly&showDetails=true"'
      hourlyUsageForToday = get_api_resource(url, params)

   return (Usage,hourlyUsageForToday)


def get_rates_of_usage(subscription_id,offerid='MS-AZR-0003p'):
   url = 'https://management.azure.com/subscriptions/'+ subscription_id +"/providers/Microsoft.Commerce/RateCard?$filter=OfferDurableId eq '"+ offerid +"' and Currency eq 'NOK' and Locale eq 'no-NO' and RegionInfo eq 'NO'"
   params = {'api-version': '2015-06-01-preview' }
   rates =  get_api_resource(url, params)
   #print (rates.request.response)
   #pprint(vars(rates))
   #print(json.dumps(rates.json(), indent=4, separators=(',', ': ')))
   return rates


def GetMeterRate(meterRates, includedqty, usedqty, qtytoadd):
   modified_rates = {}
   #pprint(includedqty)
   if includedqty > 0:
     modified_rates = {str(float(k)+includedqty):v for k,v in meterRates.items() }
   else:
     modified_rates = meterRates
   #pprint(modified_rates)
   costs = 0.0
   billqty = 0.0

   for i, (rqty, rvalue) in enumerate(modified_rates.items()):
     totalUsed = usedqty + qtytoadd
     tmp = totalUsed - float(rqty)

     if tmp >=0:
       if tmp > qtytoadd:
          tmp = qtytoadd
       costs += tmp * rvalue

       if rvalue > 0:
          billqty += tmp
       qtytoadd -=tmp

       if qtytoadd == 0:
          break

   return (costs,billqty)



   
def combinecost(Usage,rate_cards,showDetails=False): 
   uniqmeterIDs = list(set([json_dict['properties']['meterId'] for json_dict in Usage.json()['value']]))
   agg_qty = {meterid:{} for meterid in uniqmeterIDs }
   resourceCosts = 0.0
   #print(json.dumps(Usage.json(), indent=4, separators=(',', ': ')))
   #print(agg_qty['12da282f-7e96-49e2-983a-9a65da2a4866'])

   for eachusage in Usage.json()['value']:
      meterId = eachusage['properties']['meterId']
      billcycleId = dateutil.parser.parse(eachusage['properties']['usageStartTime'])
      #billcycleId = eachusage['properties']['usageStartTime']
      ratecard = [r for r in rate_cards.json()['Meters'] if r['MeterId'] == meterId ][0]

      if not billcycleId in agg_qty[meterId]:
        agg_qty[meterId][billcycleId]={'usage':0.0}

      used_quantity = agg_qty[meterId][billcycleId]['usage']
      curcosts, billableunits = GetMeterRate(ratecard['MeterRates'],ratecard['IncludedQuantity'],used_quantity,eachusage['properties']['quantity'])
      #pprint (curcosts)
      agg_qty[meterId][billcycleId]['usage']+=eachusage['properties']['quantity']
      agg_qty[meterId][billcycleId]['costs']= curcosts
      agg_qty[meterId][billcycleId]['BillableUnits']= billableunits


      #resourceCosts = [{'RateCardMeter':ratecard,'UsageValue':eachusage, 'CalculatedCosts': curcosts, 'BillableUnits': billableunits }]

   for meterid in agg_qty:
     ratecard = [ r for r in rate_cards.json()['Meters'] if r['MeterId'] == meterid ][0]
     meterCategory=ratecard['MeterCategory']
     MeterName= ratecard['MeterName']
     if showDetails == True:
         print (meterCategory+ "  " + MeterName)
     for billcycleId in agg_qty[meterid]:
        #pprint(agg_qty[meterid][billcycleId])
        resourceCosts += agg_qty[meterid][billcycleId]['costs']
        #print (str(agg_qty[meterid][billcycleId]['BillableUnits']))
        if showDetails == True:
          print ("====>" + billcycleId.isoformat() +"   cost:" + str(agg_qty[meterid][billcycleId]['costs']) + "  Usage:"+str(agg_qty[meterid][billcycleId]['BillableUnits']))

   if showDetails == True:
       print("TotalCost:"+str(resourceCosts))
   return resourceCosts
   

   

  

def main():
  parser = argparse.ArgumentParser(description='Calcutates the total cost from all billing cycle till date')
  parser.add_argument('--resolution', type=str,default="Daily",help='Get the costs incurred Daily or Hourly (default=Daily)')
  parser.add_argument('--details', action='store_true', help='Show a breakdown of cost for each resource incurred according to resolution')
  args = parser.parse_args()

  subscriptions = get_subscriptions()
  resolution = args.resolution
  for subscription in (subscriptions.json())['value']: 
     #print( subscription['subscriptionId'])
     periods=get_billing_periods( subscription['subscriptionId'])
     rate_cards=get_rates_of_usage(subscription['subscriptionId'])
     TotalCosts={}
     for period in (periods.json())['value']:
       #print( period['name'])
       Usage, hourlyUsageForToday = get_usage_for_billing_period( subscription['subscriptionId'], period['properties']['billingPeriodStartDate'],period['properties']['billingPeriodEndDate'],resolution)

       if 'value' in Usage.json():
          Total=combinecost(Usage,rate_cards,args.details)
          if hourlyUsageForToday is not None:
            Total+=combinecost(hourlyUsageForToday,rate_cards,args.details)

          print("GrandTotalCost:"+str(Total))
       else:
          print(json.dumps(Usage.json(), indent=4, separators=(',', ': ')))


main()
