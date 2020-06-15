from datetime import date, datetime, timedelta
import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from plotly.offline import plot
from pandas import ExcelFile, ExcelWriter
from io import BytesIO
from . import db, conn, engine


# TODO ###################################################################
# 
# - do I keep the users table running at all times??
# - how do i handle teardown of temp table?
# - what is the best way to query the data in temp to make new data?
# - how is the database file actually getting created?
# - is there a better way to rebuild the users table?
#
# - also would be good to modularize the blob boundaries
##########################################################################

# FUNCTIONS ##############################################################

# Find first instance of a cell to calculate blob boundaries
def find_first_address(df, string):
    coordList = []
    result = df.isin([string])
    obj = result.any()
    cols = list(obj[obj == True].index)
    for c in cols:
        rows = list(result[c][result[c]==True].index)
        for r in rows:
            coordList.append((r,c))
    return coordList[0]

# Convert a dataframe to a list, with only non-null values
def to_list(df):
    valList = []
    for row in df.values:
        for cell in row:
            if str(cell) != 'nan' and str(cell) != 'None':
                valList.append(cell)
    return valList

# Remove weird chars from list
def remove_char(list):
    return [e.replace('\n', '').replace(':', '') for e in list]

# Convert the list into a dictionary
def to_dict(list):
    return {list[i]:list[i+1] for i in range(0, len(list), 2)}

# Calculate Past Due Bucket
def days_past_due_to_buckets(x):  
    val = int(x['Days Past Due']) 
    if (val > 0) & (val <= 30):
        return '1-30 Days'
    elif (val > 30) & (val <= 60):
        return '31-60 Days'
    elif (val > 60) & (val <= 90):
        return '61-90 Days'
    elif (val > 90) & (val <= 120):
        return '91-120 Days'
    elif (val > 120) & (val <= 180):
        return '121-180 Days'
    elif val > 180:
        return '181+ Days'
    else:
        return 'Current'

# Calculate how many days until the next Past Due Bucket 
def days_past_due_to_alert_date(df, col):
    in_bucket = (df[col]/30).apply(np.floor)
    next_bucket = in_bucket + 1
    day_diff = (next_bucket*30) - df[col]
    alert_date = datetime.now() + pd.TimedeltaIndex(day_diff, unit='D')
    return alert_date


# The big kahuna
def generate_tabnonsum(excel_file, commit = 0):
    # Set initial sample (40Rx40C)
    dfInputSample = excel_file.iloc[0:40,0:40]

    # Set initial blob boundaries
    blobCustTopLeft = find_first_address(dfInputSample, 'Customer:')
    blobCustBottomRight = find_first_address(dfInputSample, '121-180 Days')
    blobInvoiceTopLeft = find_first_address(dfInputSample, 'Document Number')
    blobInvoiceTopRight = find_first_address(dfInputSample, 'Total\n\n')

    # Initialize the final dataset, which will be copied to site.db
    dfTabNonsum = pd.DataFrame(index=None)

    eof = False
    # Main loop
    while eof == False:
        # Define customer blob as a dataframe of the input excel file.  The size is based on the blob boundaries above.
        customerBlob = excel_file.iloc[blobCustTopLeft[0]:blobCustBottomRight[0], blobCustTopLeft[1]:blobCustBottomRight[1]]

        # Transform customer blob into dictionary, which will be cross joined to all records of invoice blob
        listCustomerInfo = remove_char(to_list(customerBlob))
        dictCustomerInfo = to_dict(listCustomerInfo)

        #Count invoices
        invoiceCount = 0 
        headerOffset = 1
        while str(excel_file.loc[blobInvoiceTopLeft[0] + headerOffset + invoiceCount, blobInvoiceTopLeft[1]]) != 'nan':
            invoiceCount += 1

        #Define invoice blob as df
        invoiceBlob = excel_file.iloc[blobInvoiceTopLeft[0]:blobInvoiceTopLeft[0] + headerOffset + invoiceCount,
                                blobInvoiceTopLeft[1]:blobInvoiceTopRight[1] + headerOffset]

        #Transform invoice blob into a dataframe
        invoiceBlob = invoiceBlob.dropna(axis=1, how='all')
        headers = remove_char(invoiceBlob.iloc[0])
        invoiceBlob = invoiceBlob[1:]
        invoiceBlob.columns = headers
        invoiceBlob['key']=0

        #Append the intermediate data set to the rolling data set
        dfIntermediate = pd.DataFrame([dictCustomerInfo], index=None)
        dfIntermediate['key'] = 0 #this is used as the key for the cross-join
        dfIntermediate = dfIntermediate.merge(invoiceBlob, how='outer') #cross-join
        dfTabNonsum = pd.concat([dfTabNonsum, dfIntermediate], ignore_index=True, sort=False)
        
        #Set boundaries for new blobs... end loop if no next 'Customer:' is found
        try:
            usedBlobsOffset = blobCustTopLeft[0]+len(customerBlob)+len(invoiceBlob)
            dfInputSample = excel_file.iloc[usedBlobsOffset:usedBlobsOffset+40, 0:40]
            blobCustTopLeft = find_first_address(dfInputSample, 'Customer:')
            blobCustBottomRight = find_first_address(dfInputSample, '121-180 Days')
            blobInvoiceTopLeft = find_first_address(dfInputSample, 'Document Number')
            blobInvoiceTopRight = find_first_address(dfInputSample, 'Total\n\n')
        except: #only time this will fail is if find_first_address('Customer:') fails
            eof = True
    
    #Reformatting TabNonsum
    dfTabNonsum.rename(columns={'Date': 'Invoice Date', 'Total': 'Invoice Amount'}, inplace=True)
    dfTabNonsum = dfTabNonsum.drop(labels=['key','Amount','Current','1-30 Days',
                                           '31-60 Days','61-90 Days','91-120 Days',
                                          '121-180 Days','181 and Over'], axis=1)
    dfTabNonsum['Credit'] = np.where(dfTabNonsum['Invoice Amount']<0, 1, 0)
    dfTabNonsum['Run Date'] = datetime.now()
    dfTabNonsum['Past Due'] = np.where(dfTabNonsum['Run Date']>=dfTabNonsum['Due Date'], 1, 0)
    dfTabNonsum['Days Past Due'] = np.where(dfTabNonsum['Past Due']==1, 
                                        (pd.to_datetime(dfTabNonsum['Run Date']) - 
                                         pd.to_datetime(dfTabNonsum['Due Date'])).dt.days, 0)
    dfTabNonsum['Past Due Bucket Int'] = np.where(dfTabNonsum['Past Due']==1, np.ceil(dfTabNonsum['Days Past Due']/30) * 30, 0)
    dfTabNonsum['At Risk'] = np.where(dfTabNonsum['Past Due Bucket Int'] - dfTabNonsum['Days Past Due'] <= 10, 1, 0)
    dfTabNonsum['Past Due Bucket'] = dfTabNonsum.apply(days_past_due_to_buckets, axis=1)
    dfTabNonsum['Next Alert Date'] = days_past_due_to_alert_date(dfTabNonsum, 'Days Past Due')
    dfTabNonsum['As of Date'] = excel_file.iloc[0,7].split()[-1]

    if commit == False:
        dfTabNonsum.to_sql('TEMPNonsum', con = conn, if_exists = 'replace')
        # need to do a teardown of this table after the connection is closed
    else:
        dfTabNonsum.to_sql('PRODNonsum', con = conn, if_exists = 'replace') 


def generate_tabsum(commit = 0):
    dfTabSum = pd.read_sql_query('''
        select 
            Customer
            ,Name
            ,sum(1) as [Invoice Count]
            ,sum([Past Due]) as [Past Due Count]
            ,max([Days Past Due]) as [Max Days Past Due]
            ,round(avg([Days Past Due]),0) as [Average Days Past Due]
            ,round(sum([Past Due])/sum(1.00),2) as [Past Due Percent]
            ,round(sum([Invoice Amount]),2) as [Total Invoice Amount]
            ,round(max([Invoice Amount]),2) as [Max Invoice Amount]
            ,round(avg([Invoice Amount]),2) as [Average Invoice Amount]
        from 
            TEMPNonsum 
        group by
            Customer
            ,Name
                                    ''' , con = conn)

    if commit == False:
        dfTabSum.to_sql('TEMPSum', con = conn, if_exists = 'replace')
        # need to do a teardown of this table after the connection is closed
    else:
        dfTabSum.to_sql('PRODSum', con = conn, if_exists = 'replace') 


def write_to_excel():
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter', datetime_format = '%m/%d/%y')

    dfTabNonsum = pd.read_sql_query('''
        select 
            Customer
            ,Name
            ,Phone
            ,Terms
            ,Contact
            ,trim([Document Number]) as [Document Number]
            ,Type
            ,date([Invoice Date]) as [Invoice Date]
            ,date([Due Date]) as [Due Date]
            ,cast([Invoice Amount] as integer) as [Invoice Amount]
            ,case Credit when 1 then 'Credit' else 'Debit' end as [Credit or Debit]
            ,case [Past Due] when 1 then 'Past Due' else 'Current' end as [Past Due?]
            ,[Days Past Due]
            ,case [At Risk] when 1 then 'At Risk' else 'Not At Risk' end as [At Risk?]
            ,[Past Due Bucket]
            ,date([Next Alert Date]) as [Next Alert Date]
        from
            TEMPNonsum
                                    ''', con = conn)
    dfTabSum = pd.read_sql_query('select * from TEMPSum', con = conn)

    #Formats
    money_fmt = writer.book.add_format({'num_format': '$#,##0'})
    number_fmt = writer.book.add_format({'num_format': '#,##0'})
    percent_fmt = writer.book.add_format({'num_format': '0%'})
    column_formats = {'Invoice Amount': money_fmt, 'Days Past Due' : number_fmt, 'Invoice Count' : number_fmt, 
                    'Invoice Count' : number_fmt, 'Past Due Count' : number_fmt, 
                    'Max Days Past Due' : number_fmt, 'Average Days Past Due' : number_fmt,
                    'Past Due Percent' : percent_fmt, 'Total Invoice Amount' : money_fmt,
                    'Max Invoice Amount' : money_fmt, 'Average Invoice Amount' : money_fmt
    }

    def column_format(df, sheet_name):
        for col in df:
            column_length = max(df[col].astype(str).map(len).max(), len(col))
            column_index = df.columns.get_loc(col)
            if col in column_formats.keys():
                column_format = column_formats[col]
            else:
                column_format = None
            writer.sheets[sheet_name].set_column(column_index, column_index, column_length, column_format)

    dfTabNonsum.to_excel(writer, sheet_name='Unsummarized Data', index=False)
    dfTabSum.to_excel(writer, sheet_name='Summarized Data', index=False)
    column_format(dfTabNonsum, 'Unsummarized Data')
    column_format(dfTabSum, 'Summarized Data')
    writer.close()
    output.seek(0)
    return output 


def word_dicts(boolHistorical):
    if boolHistorical == True:
        dfTabNonsum = pd.read_sql('PRODNonsum', con = conn)
    else:
        dfTabNonsum = pd.read_sql('TEMPNonsum', con = conn)
        
    as_of_date = dfTabNonsum['As of Date'].iloc[0]

    #Generate the date variables
    today = datetime.now()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    this_saturday = last_sunday + timedelta(days=6)
    next_sunday = last_sunday + timedelta(days=7)
    next_saturday = this_saturday + timedelta(days=7)

    #Calculate Datasets for TW and NW.  DEBITS ONLY!
    dfTW = dfTabNonsum[(dfTabNonsum['Next Alert Date'] >= last_sunday) & (dfTabNonsum['Next Alert Date'] <= this_saturday) & (dfTabNonsum['Credit'] == 0)] 
    dfNW = dfTabNonsum[(dfTabNonsum['Next Alert Date'] >= next_sunday) & (dfTabNonsum['Next Alert Date'] <= next_saturday) & (dfTabNonsum['Credit'] == 0)]
    
    #Pandas converts this to 'object' dtype for some reason
    dfTW['Invoice Amount'] = dfTW['Invoice Amount'].astype(float)
    dfNW['Invoice Amount'] = dfNW['Invoice Amount'].astype(float)

    #This week words
    countTW = len(dfTW)
    sumTW = dfTW['Invoice Amount'].sum()
    maxTW = dfTW['Invoice Amount'].max()
    docTW = dfTW['Document Number'][dfTW['Invoice Amount'] == maxTW].iloc[0] #oldest doc number
    docCompanyTW = dfTW['Name'][dfTW['Document Number'] == docTW].iloc[0] #name of the company with oldest doc number
    sumByCompanyTW = dfTW.groupby('Name')['Invoice Amount'].sum()
    sumMaxDueByCompanyTW = sumByCompanyTW.max()
    sumDueCompanyNameTW = sumByCompanyTW.index[sumByCompanyTW == sumMaxDueByCompanyTW][0].strip() #returns company name
    countByCompanyTW = dfTW.groupby('Name')['Invoice Amount'].count()
    countMaxDueByCompanyTW = countByCompanyTW.max()
    countDueCompanyNameTW = countByCompanyTW.index[countByCompanyTW == countMaxDueByCompanyTW][0].strip()

    #Next week words
    countNW = len(dfNW)
    sumNW = dfNW['Invoice Amount'].sum()
    maxNW = dfNW['Invoice Amount'].max()
    docNW = dfNW['Document Number'][dfNW['Invoice Amount'] == maxNW].iloc[0] #oldest doc number
    docCompanyNW = dfNW['Name'][dfNW['Document Number'] == docNW].iloc[0] #name of the company with oldest doc number
    sumByCompanyNW = dfNW.groupby('Name')['Invoice Amount'].sum()
    sumMaxDueByCompanyNW = sumByCompanyNW.max()
    sumDueCompanyNameNW = sumByCompanyNW.index[sumByCompanyNW == sumMaxDueByCompanyNW][0].strip()
    countByCompanyNW = dfNW.groupby('Name')['Invoice Amount'].count()
    countMaxDueByCompanyNW = countByCompanyNW.max()
    countDueCompanyNameNW = countByCompanyNW.index[countByCompanyNW == countMaxDueByCompanyNW][0].strip()

    #Build a dictionary for the render_template
    word_dictionary = {
        'as_of_date' : as_of_date,
        'last_sunday' : last_sunday.strftime('%B %d'),
        'this_saturday' : this_saturday.strftime('%B %d'),
        'countTW' : f'{countTW:,.0f}',
        'sumTW' : f'{sumTW:,.0f}',
        'maxTW' : f'{maxTW:,.0f}',
        'docTW' : docTW,
        'docCompanyTW' : docCompanyTW,
        'sumMaxDueByCompanyTW' : f'{sumMaxDueByCompanyTW:,.0f}',
        'sumDueCompanyNameTW' : sumDueCompanyNameTW,
        'countMaxDueByCompanyTW' : f'{countMaxDueByCompanyTW:,.0f}',
        'countDueCompanyNameTW' : countDueCompanyNameTW,
        'next_sunday' : next_sunday.strftime('%B %d'),
        'next_saturday' : next_saturday.strftime('%B %d'),
        'countNW' : f'{countNW:,.0f}',
        'sumNW' : f'{sumNW:,.0f}',
        'maxNW' : f'{maxNW:,.0f}',
        'docNW' : docNW,
        'docCompanyNW' : docCompanyNW,
        'sumMaxDueByCompanyNW' : f'{sumMaxDueByCompanyNW:,.0f}',
        'sumDueCompanyNameNW' : sumDueCompanyNameNW,
        'countMaxDueByCompanyNW' : f'{countMaxDueByCompanyNW:,.0f}',
        'countDueCompanyNameNW' : countDueCompanyNameNW
    }

    return word_dictionary


def graph_this_week(boolHistorical):
    #Generate the date variables
    today = datetime.now()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    this_saturday = last_sunday + timedelta(days=6)

    if boolHistorical == True:
        source = 'PRODNonsum'
    else:
        source = 'TEMPNonsum'

    dfTW = pd.read_sql_query('''
    select
        trim(substr([Past Due Bucket], 1, instr([Past Due Bucket],' '))) as [Days Past Due]
        ,sum([Invoice Amount]) as [Past Due Balances]
        ,'n=' || cast(count(distinct [Document Number]) as string) as [Past Due Invoices]
    from
        {}
    where
        [Next Alert Date] between '{}' and '{}'
        and [Past Due Bucket] <> 'Current'
    group by
        [Past Due Bucket]
                                '''.format(source, last_sunday, this_saturday), con = conn)

    graphTW = px.bar(dfTW, x ='Days Past Due', y = 'Past Due Balances', text = 'Past Due Invoices', template = 'plotly_white',
                                    category_orders = {'Days Past Due': ['1-30','31-60','61-90','91-120','121-180','181+']} ) 
    graphTW.update_traces(textposition = 'outside', textfont_size = 10)
    graphTW.update_yaxes(title_text = 'Past Due Balances', tickformat = '$,.0f')
    graphTW.update_layout(paper_bgcolor='#F8F9fa', plot_bgcolor='#F8F9fa')
    divtext = plot(graphTW, include_plotlyjs = False, output_type='div', config={'displayModeBar': False})
    return divtext


def graph_next_week(boolHistorical):
    #Generate the date variables
    today = datetime.now()
    last_sunday = today - timedelta(days=today.weekday() + 1)
    this_saturday = last_sunday + timedelta(days=6)
    next_sunday = last_sunday + timedelta(days=7)
    next_saturday = this_saturday + timedelta(days=7)

    if boolHistorical == True:
        source = 'PRODNonsum'
    else:
        source = 'TEMPNonsum'

    dfTW = pd.read_sql_query('''
    select
        trim(substr([Past Due Bucket], 1, instr([Past Due Bucket],' '))) as [Days Past Due]
        ,sum([Invoice Amount]) as [Past Due Balances]
        ,'n=' || cast(count(distinct [Document Number]) as string) as [Past Due Invoices]
    from
        {}
    where
        [Next Alert Date] between '{}' and '{}'
        and [Past Due Bucket] <> 'Current'
    group by
        [Past Due Bucket]
                                '''.format(source, next_sunday, next_saturday), con = conn)

    graphNW = px.bar(dfTW, x ='Days Past Due', y = 'Past Due Balances', text = 'Past Due Invoices', template = 'plotly_white', 
                                    category_orders = {'Days Past Due': ['1-30','31-60','61-90','91-120','121-180','181+']}) 

    graphNW.update_traces(textposition = 'outside', textfont_size = 10)
    graphNW.update_yaxes(title_text = 'Past Due Balances', tickformat = '$,.0f')
    graphNW.update_layout(paper_bgcolor='#F8F9fa', plot_bgcolor='#F8F9fa')
    
    divtext = plot(graphNW, include_plotlyjs = False, output_type='div', config={'displayModeBar': False})
    return divtext



def graph_at_risk(boolHistorical):

    if boolHistorical == True:
        source = 'PRODNonsum'
    else:
        source = 'TEMPNonsum'

    dfAtRisk = pd.read_sql_query('''
    select
        [Past Due Bucket]
        ,sum([At Risk]) as [Count At Risk]
        ,cast(round(sum([At Risk])/sum(1.0),3)*100 as string) || '%' as [Percent At Risk]
    from
        {}
    where
        [Past Due Bucket] <> 'Current'
    group by
        [Past Due Bucket]
                                '''.format(source), con = conn)
 
    graphAtRisk = px.bar(dfAtRisk, x = 'Past Due Bucket', y = 'Count At Risk', text = 'Percent At Risk', template = 'plotly_white', category_orders={'Past Due Bucket' : ['1-30 Days','31-60 Days','61-90 Days','91-120 Days','121-180 Days','181+ Days']} )
    graphAtRisk.update_traces(textposition = 'outside', textfont_size = 10)
    graphAtRisk.update_xaxes(title_text = None)
    return plot(graphAtRisk, include_plotlyjs = False, output_type='div')


def graph_top_five():
    dfTopFive = pd.read_sql_query('''
    
    
                                ''', con = conn)



def drop_temp():
    pass