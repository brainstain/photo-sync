from __future__ import annotations
from typing import Optional
import json
from synology_api import photos

class Photos(photos.Photos):

    def __init__(self,
                 ip_address: str,
                 port: str,
                 username: str,
                 password: str,
                 secure: bool = False,
                 cert_verify: bool = False,
                 dsm_version: int = 7,
                 debug: bool = True,
                 otp_code: Optional[str] = None,
                 ) -> None:

        super(Photos, self).__init__(ip_address, port, username, password, secure, cert_verify,
                                     dsm_version, debug, otp_code)

    # https://<IP_ADDRESS>/photo/webapi/entry.cgi?api=SYNO.Foto.Search.Search&method=list_item
    # &version=1&offset=0&limit=10&keyword=%22Iceland%22


    def get_album_items(self, album_name: str, additional: Optional[str | list[str]] = None) -> dict[str, object] | str:
        if additional is None:
            additional = []
        api_name = 'SYNO.Foto.Search.Search'
        req_param = {'version': '6', 'keyword': json.dumps(album_name), 'offset': '0', 'limit': '500', 
                     'method': 'list_item',
                     'additional': json.dumps(additional)}
        
        return self.request_data(api_name, 'entry.cgi/SYNO.Foto.Search.Search', req_param, method='post')
    
    @staticmethod
    def parse_items(items: list[object]) -> dict[str,str]:
        parsed_items = {}
        for item in items:
            parsed_items[item['additional']['thumbnail']['cache_key']] = item['additional']['thumbnail']['unit_id']
        return parsed_items

    def download_item(self, cache_key: str, unit_id: str):
        api_name = 'SYNO.Foto.Download'
        req_param = {'version': '2', 'method': 'download', 'download_type': 'optimized_jpeg','cache_key': cache_key, 'unit_id': json.dumps([unit_id])}
        return self.request_data(api_name, 'entry.cgi', req_param, method='get', response_json=False)

