from fastapi.security import OAuth2
from keycloak import KeycloakOpenID # pip require python-keycloak
from fastapi import Security, HTTPException, status,Depends

server_url="https://auth.coramaps.com"
realm="services"
client_id="health_check_api"
client_secret=""
token_url="https://auth.coramaps.com/realms/services/protocol/openid-connect/token"
auth_url="https://auth.coramaps.com/realms/services/protocol/openid-connect/auth"


# Define the all supported OAuth2 authorization grant types.
# Here, we support `password` (intended for scripts / maschines) and
# `authorizationCode` (intended for humans e.g. using postman)
oauth = OAuth2(
    flows={
        "password": {
            "tokenUrl":token_url,
            "clientId":client_id

        },
        "authorizationCode": {
            "authorizationUrl": auth_url,
            "tokenUrl": token_url,
            "clientId":client_id
        }
    }, 
    scheme_name="OAuth2 using either 'password' or 'authorization code' grant type",
    description="The authorization uses OAuth2 access tokens. You can use either the `password` or the `authorization code` flow. More info can be found in the [authentication section](/#section/Authentication)")


# This actually does the auth checks
# client_secret_key is not mandatory if the client is public on keycloak
keycloak_openid = KeycloakOpenID(
    server_url=server_url,
    client_id=client_id, # backend-client-id
    realm_name=realm, # example-realm
    client_secret_key=client_secret, # your backend client secret
    verify=True
)

# Get the payload/token from keycloak
async def get_payload(token: str = Security(oauth)) -> dict:
    try:
        if "Bearer" in token: # remove `Bearer` from token
            token = token.split(" ")[1]
        return keycloak_openid.decode_token(
            token,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e), # "Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Get user_group_list from the payload
async def get_user_info(payload: dict = Depends(get_payload)) -> list[str]:
    try:
        if client_id not in payload["resource_access"]:
            raise PermissionError('User is not allowed to use this resource')
        # first, let's check if the user is allowed to use the service
        # if client_id in payload["resource_access"]:
        #     roles = payload["resource_access"][client_id]["roles"]
        #     # raise execption if user don't have the role 'use-service'
        #     if "use-service" not in roles:
        #         raise PermissionError('User is not allowed to use this resource')
        # else:
        #     raise PermissionError('User is not allowed to use this resource')

        # ok, the user is allowed to use the service, return groups
        return payload.get("groups", [])
    
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(pe), headers={"WWW-Authenticate": "Bearer"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e), # "Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# async def get_client_names_from_user(user_group_list: list[str] = Depends(get_user_info)) -> list[str]:
#     try:
#         client_names = [group[1:].replace('/','-') for group in user_group_list]
        
#         if not client_names:
#             raise
#         return client_names

#     except Exception as e:
#         raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail=f"There are no authorized fields for the user. {e}",
#             )



