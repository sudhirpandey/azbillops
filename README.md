# Usage
 - Make sure you have created relevant service account in azure with appropriate role to be able to read from given subscription . This can be achieved by following one of the method described [here](https://docs.microsoft.com/en-us/azure/azure-resource-manager/resource-group-create-service-principal-portal?view=azure-cli-latest)
 - fill up the relevant section of cred.sh file to hold appropriate value
 -  ```
    sh -x cred.sh 
    python getcost.py 
    ```
 - View breakdown of cost for each resource involved under each hour 
   ```
   python getcost.py --resolution=Hour --details
   ```

# To do list
- Make self sufficent dockerfile to get container image.
- Make start date paramaterized 
- Have parameter to hook up with slack Url for notification if cost exceepts
- Possibly be able to shutdown resources that are generating most cost
